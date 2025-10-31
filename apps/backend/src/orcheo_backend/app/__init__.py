"""FastAPI application entrypoint for the Orcheo backend service."""

from __future__ import annotations
import asyncio
import json
import logging
import os
import secrets
import uuid
from collections.abc import Mapping
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal, NoReturn, cast
from uuid import UUID
from chatkit.server import StreamingResult
from chatkit.types import ChatKitReq
from dotenv import load_dotenv
from dynaconf import Dynaconf
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.runnables import RunnableConfig
from pydantic import TypeAdapter, ValidationError
from starlette.responses import JSONResponse, StreamingResponse
from orcheo.config import get_settings
from orcheo.graph.builder import build_graph
from orcheo.graph.ingestion import (
    LANGGRAPH_SCRIPT_FORMAT,
    ScriptIngestionError,
    ingest_langgraph_script,
)
from orcheo.graph.state import State
from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialIssuancePolicy,
    CredentialKind,
    CredentialMetadata,
    CredentialScope,
    CredentialTemplate,
    OAuthTokenSecrets,
    SecretGovernanceAlert,
)
from orcheo.models.workflow import Workflow, WorkflowRun, WorkflowVersion
from orcheo.persistence import create_checkpointer
from orcheo.runtime.credentials import CredentialResolver, credential_resolution
from orcheo.triggers.cron import CronTriggerConfig
from orcheo.triggers.manual import ManualDispatchRequest
from orcheo.triggers.webhook import WebhookTriggerConfig, WebhookValidationError
from orcheo.vault import (
    BaseCredentialVault,
    CredentialNotFoundError,
    CredentialTemplateNotFoundError,
    DuplicateCredentialNameError,
    FileCredentialVault,
    GovernanceAlertNotFoundError,
    InMemoryCredentialVault,
    WorkflowScopeError,
)
from orcheo.vault.oauth import (
    CredentialHealthError,
    CredentialHealthReport,
    OAuthCredentialService,
)
from orcheo_backend.app.chatkit_service import (
    ChatKitRequestContext,
    OrcheoChatKitServer,
    create_chatkit_server,
)
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore
from orcheo_backend.app.history import (
    InMemoryRunHistoryStore,
    RunHistoryNotFoundError,
    RunHistoryRecord,
    RunHistoryStore,
    SqliteRunHistoryStore,
)
from orcheo_backend.app.repository import (
    InMemoryWorkflowRepository,
    WorkflowNotFoundError,
    WorkflowRepository,
    WorkflowRunNotFoundError,
    WorkflowVersionNotFoundError,
)
from orcheo_backend.app.repository_sqlite import SqliteWorkflowRepository
from orcheo_backend.app.schemas import (
    AlertAcknowledgeRequest,
    ChatKitSessionRequest,
    ChatKitSessionResponse,
    ChatKitWorkflowTriggerRequest,
    CredentialCreateRequest,
    CredentialHealthItem,
    CredentialHealthResponse,
    CredentialIssuancePolicyPayload,
    CredentialIssuanceRequest,
    CredentialIssuanceResponse,
    CredentialScopePayload,
    CredentialTemplateCreateRequest,
    CredentialTemplateResponse,
    CredentialTemplateUpdateRequest,
    CredentialValidationRequest,
    CredentialVaultEntryResponse,
    CronDispatchRequest,
    GovernanceAlertResponse,
    NodeExecutionRequest,
    NodeExecutionResponse,
    OAuthTokenRequest,
    RunActionRequest,
    RunCancelRequest,
    RunFailRequest,
    RunHistoryResponse,
    RunHistoryStepResponse,
    RunReplayRequest,
    RunSucceedRequest,
    WorkflowCreateRequest,
    WorkflowRunCreateRequest,
    WorkflowUpdateRequest,
    WorkflowVersionCreateRequest,
    WorkflowVersionDiffResponse,
    WorkflowVersionIngestRequest,
)


# Configure logging for the backend module once on import.
_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
_log_level_int = getattr(logging, _log_level, logging.INFO)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
)

# Set FastAPI and Orcheo loggers to the configured level
logging.getLogger("uvicorn").setLevel(_log_level_int)
logging.getLogger("uvicorn.access").setLevel(_log_level_int)
logging.getLogger("uvicorn.error").setLevel(_log_level_int)
logging.getLogger("fastapi").setLevel(_log_level_int)
logging.getLogger("orcheo").setLevel(_log_level_int)
logging.getLogger("orcheo_backend").setLevel(_log_level_int)

logger = logging.getLogger(__name__)

_DEV_LOGGING_ENV_VALUES = {"development", "dev", "local"}
_current_env = (
    os.getenv("ORCHEO_ENV")
    or os.getenv("ENVIRONMENT")
    or os.getenv(
        "NODE_ENV",
        "production",
    )
)
_sensitive_env_enabled = (_current_env or "").lower() in _DEV_LOGGING_ENV_VALUES
_should_log_sensitive_debug = (
    _sensitive_env_enabled or os.getenv("LOG_SENSITIVE_DEBUG") == "1"
)

_CHATKIT_CLEANUP_INTERVAL_SECONDS = 6 * 60 * 60
_chatkit_cleanup_task: dict[str, asyncio.Task | None] = {"task": None}


def _coerce_int(value: object, default: int) -> int:
    if isinstance(value, int):
        return value
    if value is None:
        return default
    try:
        return int(str(value))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return default


def _chatkit_retention_days() -> int:
    settings = get_settings()
    days = _coerce_int(settings.get("CHATKIT_RETENTION_DAYS", 30), 30)
    return days if days > 0 else 30


def _get_chatkit_store() -> SqliteChatKitStore | None:
    server = _chatkit_server_ref.get("server")
    if server is None:
        return None
    store = getattr(server, "store", None)
    if isinstance(store, SqliteChatKitStore):
        return store
    return None


async def _ensure_chatkit_cleanup_task() -> None:
    if _chatkit_cleanup_task["task"] is not None:
        return

    store = _get_chatkit_store()
    if store is None:
        return

    retention_days = _chatkit_retention_days()
    interval_seconds = max(_CHATKIT_CLEANUP_INTERVAL_SECONDS, 300)

    async def _cleanup_loop() -> None:
        try:
            while True:
                cutoff = datetime.now(tz=UTC) - timedelta(days=retention_days)
                try:
                    pruned = await store.prune_threads_older_than(cutoff)
                    if pruned:
                        logger.info(
                            "Pruned %s ChatKit thread(s) older than %s",
                            pruned,
                            cutoff.isoformat(),
                        )
                except asyncio.CancelledError:
                    raise
                except Exception:  # pragma: no cover - best effort logging
                    logger.exception("ChatKit cleanup task failed")

                await asyncio.sleep(interval_seconds)
        finally:
            _chatkit_cleanup_task["task"] = None

    _chatkit_cleanup_task["task"] = asyncio.create_task(
        _cleanup_loop(),
        name="chatkit_cleanup",
    )


async def _cancel_chatkit_cleanup_task() -> None:
    task = _chatkit_cleanup_task.get("task")
    if task is None:
        return

    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    _chatkit_cleanup_task["task"] = None


def _log_sensitive_debug(message: str, *args: Any) -> None:
    if _should_log_sensitive_debug:
        logger.debug(message, *args)


def _log_step_debug(step: Mapping[str, Any]) -> None:
    if not _should_log_sensitive_debug:
        return
    for node_name, node_output in step.items():
        logger.debug("=" * 80)
        logger.debug("Node executed: %s", node_name)
        logger.debug("Node output: %s", node_output)
        logger.debug("=" * 80)


def _log_final_state_debug(state_values: Mapping[str, Any] | Any) -> None:
    if not _should_log_sensitive_debug:
        return
    logger.debug("=" * 80)
    logger.debug("Final state values: %s", state_values)
    logger.debug("=" * 80)


async def _stream_workflow_updates(
    compiled_graph: Any,
    state: Any,
    config: RunnableConfig,
    history_store: RunHistoryStore,
    execution_id: str,
    websocket: WebSocket,
) -> None:
    """Stream workflow updates to the client while recording history."""
    try:
        async for step in compiled_graph.astream(
            state,
            config=config,  # type: ignore[arg-type]
            stream_mode="updates",
        ):  # pragma: no cover
            _log_step_debug(step)
            await history_store.append_step(execution_id, step)
            try:
                await websocket.send_json(step)
            except Exception as exc:  # pragma: no cover
                logger.error("Error processing messages: %s", exc)
                raise

        final_state = await compiled_graph.aget_state(cast(RunnableConfig, config))
        _log_final_state_debug(final_state.values)
    except asyncio.CancelledError as exc:
        reason = str(exc) or "Workflow execution cancelled"
        cancellation_payload = {"status": "cancelled", "reason": reason}
        await history_store.append_step(execution_id, cancellation_payload)
        await history_store.mark_cancelled(execution_id, reason=reason)
        raise
    except Exception as exc:
        error_payload = {"status": "error", "error": str(exc)}
        await history_store.append_step(execution_id, error_payload)
        await history_store.mark_failed(execution_id, str(exc))
        raise


load_dotenv()

_ws_router = APIRouter()
_http_router = APIRouter(prefix="/api")
_repository: WorkflowRepository
_history_store_ref: dict[str, RunHistoryStore] = {"store": InMemoryRunHistoryStore()}
_credential_service_ref: dict[str, OAuthCredentialService | None] = {"service": None}
_vault_ref: dict[str, BaseCredentialVault | None] = {"vault": None}


def _settings_value[T](
    settings: Any, *, attr_path: str | None, env_key: str, default: T
) -> T:
    """Return a configuration value supporting Dynaconf and attribute objects."""
    if hasattr(settings, "get"):
        try:
            value = settings.get(env_key, default)
        except TypeError:  # pragma: no cover - defensive fallback
            value = default
        return cast(T, value)

    if attr_path:  # pragma: no branch - simple attribute walk
        current = settings
        for part in attr_path.split("."):
            if not hasattr(current, part):
                break
            current = getattr(current, part)
        else:
            return cast(T, current)

    return default


def _ensure_file_vault_key(path: Path, provided_key: str | None) -> str:
    """Load the encryption key for a file-backed vault, generating it when missing."""
    if provided_key:
        return provided_key
    key_path = path.with_name(f"{path.stem}.key")
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        key = key_path.read_text(encoding="utf-8").strip()
        if key:
            return key
    key = secrets.token_hex(32)
    key_path.write_text(key, encoding="utf-8")
    try:
        os.chmod(key_path, 0o600)
    except (PermissionError, NotImplementedError, OSError):
        pass
    return key


def _create_vault(settings: Dynaconf) -> BaseCredentialVault:
    backend = cast(
        str,
        _settings_value(
            settings,
            attr_path="vault.backend",
            env_key="VAULT_BACKEND",
            default="file",
        ),
    )
    key = cast(
        str | None,
        _settings_value(
            settings,
            attr_path="vault.encryption_key",
            env_key="VAULT_ENCRYPTION_KEY",
            default=None,
        ),
    )
    if backend == "inmemory":
        encryption_key = key or secrets.token_hex(32)
        cipher = AesGcmCredentialCipher(key=encryption_key)
        return InMemoryCredentialVault(cipher=cipher)
    if backend == "file":
        local_path = cast(
            str,
            _settings_value(
                settings,
                attr_path="vault.local_path",
                env_key="VAULT_LOCAL_PATH",
                default=".orcheo/vault.sqlite",
            ),
        )
        path = Path(local_path).expanduser()
        encryption_key = _ensure_file_vault_key(path, key)
        cipher = AesGcmCredentialCipher(key=encryption_key)
        return FileCredentialVault(path, cipher=cipher)
    msg = "Vault backend 'aws_kms' is not supported in this environment."
    raise ValueError(msg)


def _ensure_credential_service(settings: Dynaconf) -> OAuthCredentialService:
    service = _credential_service_ref["service"]
    if service is not None:
        return service
    vault = _vault_ref["vault"]
    if vault is None:
        vault = _create_vault(settings)
        _vault_ref["vault"] = vault
    token_ttl = cast(
        int,
        _settings_value(
            settings,
            attr_path="vault.token_ttl_seconds",
            env_key="VAULT_TOKEN_TTL_SECONDS",
            default=3600,
        ),
    )
    service = OAuthCredentialService(
        vault,
        token_ttl_seconds=token_ttl,
    )
    _credential_service_ref["service"] = service
    return service


def _create_repository() -> WorkflowRepository:
    settings = get_settings()
    service = _ensure_credential_service(settings)
    backend = cast(
        str,
        _settings_value(
            settings,
            attr_path="repository_backend",
            env_key="REPOSITORY_BACKEND",
            default="sqlite",
        ),
    )
    if backend == "sqlite":
        sqlite_path = cast(
            str,
            _settings_value(
                settings,
                attr_path="repository_sqlite_path",
                env_key="REPOSITORY_SQLITE_PATH",
                default="~/.orcheo/workflows.sqlite",
            ),
        )
        _history_store_ref["store"] = SqliteRunHistoryStore(sqlite_path)
        return SqliteWorkflowRepository(sqlite_path, credential_service=service)
    if backend == "inmemory":
        _history_store_ref["store"] = InMemoryRunHistoryStore()
        return InMemoryWorkflowRepository(credential_service=service)
    msg = "Unsupported repository backend configured."
    raise ValueError(msg)


_repository = _create_repository()


def get_repository() -> WorkflowRepository:
    """Return the singleton workflow repository instance."""
    return _repository


RepositoryDep = Annotated[WorkflowRepository, Depends(get_repository)]

_chatkit_server_ref: dict[str, OrcheoChatKitServer | None] = {"server": None}


def get_chatkit_server() -> OrcheoChatKitServer:
    """Return the singleton ChatKit server wired to the repository."""
    server = _chatkit_server_ref["server"]
    if server is None:
        server = create_chatkit_server(_repository, get_vault)
        _chatkit_server_ref["server"] = server
    return server


def get_history_store() -> RunHistoryStore:
    """Return the singleton execution history store."""
    return _history_store_ref["store"]


HistoryStoreDep = Annotated[RunHistoryStore, Depends(get_history_store)]


def get_credential_service() -> OAuthCredentialService | None:
    """Return the configured credential health service if available."""
    return _credential_service_ref["service"]


CredentialServiceDep = Annotated[
    OAuthCredentialService | None, Depends(get_credential_service)
]


def get_vault() -> BaseCredentialVault:
    """Return the configured credential vault."""
    vault = _vault_ref["vault"]
    if vault is not None:
        return vault
    settings = get_settings()
    vault = _create_vault(settings)
    _vault_ref["vault"] = vault
    return vault


VaultDep = Annotated[BaseCredentialVault, Depends(get_vault)]


WorkflowIdQuery = Annotated[UUID | None, Query()]
IncludeAcknowledgedQuery = Annotated[bool, Query()]


def _raise_not_found(detail: str, exc: Exception) -> NoReturn:
    """Raise a standardized 404 HTTP error."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
    ) from exc


def _raise_conflict(detail: str, exc: Exception) -> NoReturn:
    """Raise a standardized 409 HTTP error for conflicting run transitions."""
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
    ) from exc


def _raise_webhook_error(exc: WebhookValidationError) -> NoReturn:
    """Normalize webhook validation errors into HTTP errors."""
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _raise_scope_error(exc: WorkflowScopeError) -> NoReturn:
    """Raise a standardized 403 response for scope violations."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=str(exc),
    ) from exc


def _history_to_response(
    record: RunHistoryRecord, *, from_step: int = 0
) -> RunHistoryResponse:
    """Convert a history record into a serialisable response."""
    steps = [
        RunHistoryStepResponse(
            index=step.index,
            at=step.at,
            payload=step.payload,
        )
        for step in record.steps[from_step:]
    ]
    return RunHistoryResponse(
        execution_id=record.execution_id,
        workflow_id=record.workflow_id,
        status=record.status,
        started_at=record.started_at,
        completed_at=record.completed_at,
        error=record.error,
        inputs=record.inputs,
        steps=steps,
    )


def _health_report_to_response(
    report: CredentialHealthReport,
) -> CredentialHealthResponse:
    credentials = [
        CredentialHealthItem(
            credential_id=str(result.credential_id),
            name=result.name,
            provider=result.provider,
            status=result.status,
            last_checked_at=result.last_checked_at,
            failure_reason=result.failure_reason,
        )
        for result in report.results
    ]
    overall_status = (
        CredentialHealthStatus.HEALTHY
        if report.is_healthy
        else CredentialHealthStatus.UNHEALTHY
    )
    return CredentialHealthResponse(
        workflow_id=str(report.workflow_id),
        status=overall_status,
        checked_at=report.checked_at,
        credentials=credentials,
    )


def _scope_to_payload(scope: CredentialScope) -> CredentialScopePayload:
    return CredentialScopePayload(
        workflow_ids=list(scope.workflow_ids),
        workspace_ids=list(scope.workspace_ids),
        roles=list(scope.roles),
    )


def _policy_to_payload(
    policy: CredentialIssuancePolicy,
) -> CredentialIssuancePolicyPayload:
    return CredentialIssuancePolicyPayload(
        require_refresh_token=policy.require_refresh_token,
        rotation_period_days=policy.rotation_period_days,
        expiry_threshold_minutes=policy.expiry_threshold_minutes,
    )


def _template_to_response(template: CredentialTemplate) -> CredentialTemplateResponse:
    return CredentialTemplateResponse(
        id=str(template.id),
        name=template.name,
        provider=template.provider,
        scopes=list(template.scopes),
        description=template.description,
        kind=template.kind,
        scope=_scope_to_payload(template.scope),
        issuance_policy=_policy_to_payload(template.issuance_policy),
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _scope_from_access(
    access: Literal["private", "shared", "public"],
    workflow_id: UUID | None,
) -> CredentialScope | None:
    """Derive a credential scope from the requested access label."""
    if access == "private" and workflow_id is not None:
        return CredentialScope.for_workflows(workflow_id)

    # Shared access is not fully modelled in the prototype backend yet. Until
    # multi-tenant workspaces are introduced, treat shared credentials as
    # workflow-scoped when a workflow is provided, otherwise fall back to
    # unrestricted visibility similar to public credentials.
    if access == "shared" and workflow_id is not None:
        return CredentialScope.for_workflows(workflow_id)

    return CredentialScope.unrestricted()


def _infer_credential_access(
    scope: CredentialScope,
) -> Literal["private", "shared", "public"]:
    """Return a simplified access label derived from the scope."""
    if scope.is_unrestricted():
        return "public"

    restriction_count = (
        len(scope.workflow_ids) + len(scope.workspace_ids) + len(scope.roles)
    )

    if restriction_count <= 1:
        return "private"

    return "shared"


def _credential_to_response(
    metadata: CredentialMetadata,
) -> CredentialVaultEntryResponse:
    """Convert stored credential metadata into an API response payload."""
    owner = metadata.audit_log[0].actor if metadata.audit_log else None
    secret_preview: str | None
    if metadata.kind is CredentialKind.OAUTH:
        secret_preview = "oauth-token"
    else:
        secret_preview = "••••••••"

    return CredentialVaultEntryResponse(
        id=str(metadata.id),
        name=metadata.name,
        provider=metadata.provider,
        kind=metadata.kind,
        created_at=metadata.created_at,
        updated_at=metadata.updated_at,
        last_rotated_at=metadata.last_rotated_at,
        owner=owner,
        access=_infer_credential_access(metadata.scope),
        status=metadata.health.status,
        secret_preview=secret_preview,
    )


def _alert_to_response(alert: SecretGovernanceAlert) -> GovernanceAlertResponse:
    return GovernanceAlertResponse(
        id=str(alert.id),
        kind=alert.kind,
        severity=alert.severity,
        message=alert.message,
        credential_id=str(alert.credential_id) if alert.credential_id else None,
        template_id=str(alert.template_id) if alert.template_id else None,
        is_acknowledged=alert.is_acknowledged,
        acknowledged_at=alert.acknowledged_at,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )


def _build_scope(
    payload: CredentialScopePayload | None,
) -> CredentialScope | None:
    if payload is None:
        return None
    return CredentialScope(
        workflow_ids=list(payload.workflow_ids),
        workspace_ids=list(payload.workspace_ids),
        roles=list(payload.roles),
    )


def _build_policy(
    payload: CredentialIssuancePolicyPayload | None,
) -> CredentialIssuancePolicy | None:
    if payload is None:
        return None
    return CredentialIssuancePolicy(
        require_refresh_token=payload.require_refresh_token,
        rotation_period_days=payload.rotation_period_days,
        expiry_threshold_minutes=payload.expiry_threshold_minutes,
    )


def _build_oauth_tokens(
    payload: OAuthTokenRequest | None,
) -> OAuthTokenSecrets | None:
    if payload is None:
        return None
    return OAuthTokenSecrets(
        access_token=payload.access_token,
        refresh_token=payload.refresh_token,
        expires_at=payload.expires_at,
    )


def _context_from_workflow(
    workflow_id: UUID | None,
) -> CredentialAccessContext | None:
    if workflow_id is None:
        return None
    return CredentialAccessContext(workflow_id=workflow_id)


async def execute_workflow(
    workflow_id: str,
    graph_config: dict[str, Any],
    inputs: dict[str, Any],
    execution_id: str,
    websocket: WebSocket,
) -> None:
    """Execute a workflow and stream results over the provided websocket."""
    logger.info("Starting workflow %s with execution_id: %s", workflow_id, execution_id)
    _log_sensitive_debug("Initial inputs: %s", inputs)

    settings = get_settings()
    history_store = get_history_store()
    vault = get_vault()
    workflow_uuid: UUID | None = None
    try:
        workflow_uuid = UUID(workflow_id)
    except ValueError:
        pass
    credential_context = _context_from_workflow(workflow_uuid)
    resolver = CredentialResolver(vault, context=credential_context)
    await history_store.start_run(
        workflow_id=workflow_id, execution_id=execution_id, inputs=inputs
    )

    with credential_resolution(resolver):
        async with create_checkpointer(settings) as checkpointer:
            graph = build_graph(graph_config)
            compiled_graph = graph.compile(checkpointer=checkpointer)

            # Initialize state based on graph format
            # LangGraph scripts: pass inputs directly, letting the script define state
            # Orcheo workflows: use State class with structured fields
            is_langgraph_script = graph_config.get("format") == LANGGRAPH_SCRIPT_FORMAT
            if is_langgraph_script:
                # For LangGraph scripts, pass inputs as-is to respect the script's
                # state schema definition. The script has full control over state.
                state: Any = inputs
            else:
                # Orcheo workflows use the State class with predefined fields
                state = {
                    "messages": [],
                    "results": {},
                    "inputs": inputs,
                }
            _log_sensitive_debug("Initial state: %s", state)

            # Run graph with streaming
            config: RunnableConfig = {"configurable": {"thread_id": execution_id}}
            await _stream_workflow_updates(
                compiled_graph,
                state,
                config,
                history_store,
                execution_id,
                websocket,
            )

    completion_payload = {"status": "completed"}
    await history_store.append_step(execution_id, completion_payload)
    await history_store.mark_completed(execution_id)
    await websocket.send_json(completion_payload)  # pragma: no cover


@_ws_router.websocket("/ws/workflow/{workflow_id}")
async def workflow_websocket(websocket: WebSocket, workflow_id: str) -> None:
    """Handle workflow websocket connections by delegating to the executor."""
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "run_workflow":
                execution_id = data.get("execution_id", str(uuid.uuid4()))
                task = asyncio.create_task(
                    execute_workflow(
                        workflow_id,
                        data["graph_config"],
                        data["inputs"],
                        execution_id,
                        websocket,
                    )
                )

                await task
                break

            await websocket.send_json(  # pragma: no cover
                {"status": "error", "error": "Invalid message type"}
            )

    except Exception as exc:  # pragma: no cover
        await websocket.send_json({"status": "error", "error": str(exc)})
    finally:
        await websocket.close()


@_http_router.post("/chatkit", include_in_schema=False)
async def chatkit_gateway(request: Request) -> Response:
    """Proxy ChatKit SDK requests to the Orcheo-backed server."""
    payload = await request.body()
    try:
        adapter: TypeAdapter[ChatKitReq] = TypeAdapter(ChatKitReq)
        parsed_request = adapter.validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Invalid ChatKit payload.",
                "errors": exc.errors(),
            },
        ) from exc

    context: ChatKitRequestContext = {"chatkit_request": parsed_request}
    server = get_chatkit_server()
    result = await server.process(payload, context)

    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    if hasattr(result, "json"):
        json_payload = result.json
        status_code = getattr(result, "status_code", status.HTTP_200_OK)
        headers = getattr(result, "headers", None)
        media_type = getattr(result, "media_type", "application/json")

        if callable(json_payload):
            payload = json_payload()
        else:
            payload = json_payload

        header_mapping = dict(headers) if headers else None

        if isinstance(payload, str | bytes | bytearray):
            return Response(
                content=payload,
                status_code=status_code,
                media_type=media_type,
                headers=header_mapping,
            )

        return JSONResponse(
            payload,
            status_code=status_code,
            headers=header_mapping,
            media_type=media_type,
        )
    return JSONResponse(result)


@_http_router.post(
    "/chatkit/session",
    response_model=ChatKitSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def create_chatkit_session_endpoint(
    request: ChatKitSessionRequest,
) -> ChatKitSessionResponse:
    """Return a ChatKit client secret derived from environment configuration."""
    candidate_keys: list[str] = []
    if request.workflow_id:
        workflow_key = str(request.workflow_id).replace("-", "").upper()
        candidate_keys.append(f"CHATKIT_CLIENT_SECRET_{workflow_key}")
    candidate_keys.append("CHATKIT_CLIENT_SECRET")

    for env_key in candidate_keys:
        secret = os.getenv(env_key)
        if secret:
            logger.info("Issuing ChatKit client secret via %s", env_key)
            return ChatKitSessionResponse(client_secret=secret)

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "message": "ChatKit client secret is not configured.",
            "hint": (
                "Set CHATKIT_CLIENT_SECRET or CHATKIT_CLIENT_SECRET_<WORKFLOW_ID> "
                "in the backend environment to enable the ChatKit integration."
            ),
        },
    )


@_http_router.post(
    "/chatkit/workflows/{workflow_id}/trigger",
    response_model=WorkflowRun,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_chatkit_workflow(
    workflow_id: UUID,
    request: ChatKitWorkflowTriggerRequest,
    repository: RepositoryDep,
) -> WorkflowRun:
    """Create a workflow run initiated from the ChatKit interface."""
    try:
        latest_version = await repository.get_latest_version(workflow_id)
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)
    except WorkflowVersionNotFoundError as exc:
        _raise_not_found("Workflow version not found", exc)

    payload = {
        "source": "chatkit",
        "message": request.message,
        "client_thread_id": request.client_thread_id,
        "metadata": request.metadata,
    }

    try:
        run = await repository.create_run(
            workflow_id,
            workflow_version_id=latest_version.id,
            triggered_by=request.actor,
            input_payload=payload,
        )
    except CredentialHealthError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(exc), "failures": exc.report.failures},
        ) from exc

    logger.info(
        "Dispatched ChatKit workflow run",
        extra={"workflow_id": str(workflow_id), "run_id": str(run.id)},
    )
    return run


@_http_router.get("/workflows", response_model=list[Workflow])
async def list_workflows(
    repository: RepositoryDep,
    include_archived: bool = Query(False, description="Include archived workflows"),
) -> list[Workflow]:
    """Return workflows, excluding archived ones by default.

    Args:
        repository: Workflow repository dependency
        include_archived: If True, include archived workflows in the response

    Returns:
        List of workflows matching the filter criteria
    """
    return await repository.list_workflows(include_archived=include_archived)


@_http_router.post(
    "/workflows",
    response_model=Workflow,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow(
    request: WorkflowCreateRequest,
    repository: RepositoryDep,
) -> Workflow:
    """Create a new workflow entry."""
    return await repository.create_workflow(
        name=request.name,
        slug=request.slug,
        description=request.description,
        tags=request.tags,
        actor=request.actor,
    )


@_http_router.get("/workflows/{workflow_id}", response_model=Workflow)
async def get_workflow(
    workflow_id: UUID,
    repository: RepositoryDep,
) -> Workflow:
    """Fetch a single workflow by its identifier."""
    try:
        return await repository.get_workflow(workflow_id)
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)


@_http_router.put("/workflows/{workflow_id}", response_model=Workflow)
async def update_workflow(
    workflow_id: UUID,
    request: WorkflowUpdateRequest,
    repository: RepositoryDep,
) -> Workflow:
    """Update attributes of an existing workflow."""
    try:
        return await repository.update_workflow(
            workflow_id,
            name=request.name,
            description=request.description,
            tags=request.tags,
            is_archived=request.is_archived,
            actor=request.actor,
        )
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)


@_http_router.delete("/workflows/{workflow_id}", response_model=Workflow)
async def archive_workflow(
    workflow_id: UUID,
    repository: RepositoryDep,
    actor: str = Query("system"),
) -> Workflow:
    """Archive a workflow via the delete verb."""
    try:
        return await repository.archive_workflow(workflow_id, actor=actor)
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)


@_http_router.post(
    "/workflows/{workflow_id}/versions",
    response_model=WorkflowVersion,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_version(
    workflow_id: UUID,
    request: WorkflowVersionCreateRequest,
    repository: RepositoryDep,
) -> WorkflowVersion:
    """Create a new version for the specified workflow."""
    try:
        return await repository.create_version(
            workflow_id,
            graph=request.graph,
            metadata=request.metadata,
            notes=request.notes,
            created_by=request.created_by,
        )
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)


@_http_router.post(
    "/workflows/{workflow_id}/versions/ingest",
    response_model=WorkflowVersion,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_workflow_version(
    workflow_id: UUID,
    request: WorkflowVersionIngestRequest,
    repository: RepositoryDep,
) -> WorkflowVersion:
    """Create a workflow version from a LangGraph Python script."""
    try:
        graph_payload = ingest_langgraph_script(
            request.script,
            entrypoint=request.entrypoint,
        )
    except ScriptIngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    try:
        return await repository.create_version(
            workflow_id,
            graph=graph_payload,
            metadata=request.metadata,
            notes=request.notes,
            created_by=request.created_by,
        )
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)


@_http_router.get(
    "/workflows/{workflow_id}/versions",
    response_model=list[WorkflowVersion],
)
async def list_workflow_versions(
    workflow_id: UUID,
    repository: RepositoryDep,
) -> list[WorkflowVersion]:
    """Return the versions associated with a workflow."""
    try:
        return await repository.list_versions(workflow_id)
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)


@_http_router.get(
    "/workflows/{workflow_id}/versions/{version_number}",
    response_model=WorkflowVersion,
)
async def get_workflow_version(
    workflow_id: UUID,
    version_number: int,
    repository: RepositoryDep,
) -> WorkflowVersion:
    """Return a specific workflow version by number."""
    try:
        return await repository.get_version_by_number(workflow_id, version_number)
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)
    except WorkflowVersionNotFoundError as exc:
        _raise_not_found("Workflow version not found", exc)


@_http_router.get(
    "/workflows/{workflow_id}/versions/{base_version}/diff/{target_version}",
    response_model=WorkflowVersionDiffResponse,
)
async def diff_workflow_versions(
    workflow_id: UUID,
    base_version: int,
    target_version: int,
    repository: RepositoryDep,
) -> WorkflowVersionDiffResponse:
    """Generate a diff between two workflow versions."""
    try:
        diff = await repository.diff_versions(workflow_id, base_version, target_version)
        return WorkflowVersionDiffResponse(
            base_version=diff.base_version,
            target_version=diff.target_version,
            diff=diff.diff,
        )
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)
    except WorkflowVersionNotFoundError as exc:
        _raise_not_found("Workflow version not found", exc)


@_http_router.post(
    "/workflows/{workflow_id}/runs",
    response_model=WorkflowRun,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_run(
    workflow_id: UUID,
    request: WorkflowRunCreateRequest,
    repository: RepositoryDep,
    _service: CredentialServiceDep,
) -> WorkflowRun:
    """Create a workflow execution run."""
    try:
        return await repository.create_run(
            workflow_id,
            workflow_version_id=request.workflow_version_id,
            triggered_by=request.triggered_by,
            input_payload=request.input_payload,
        )
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)
    except WorkflowVersionNotFoundError as exc:
        _raise_not_found("Workflow version not found", exc)
    except CredentialHealthError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(exc), "failures": exc.report.failures},
        ) from exc


@_http_router.get(
    "/credentials",
    response_model=list[CredentialVaultEntryResponse],
)
def list_credentials(
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> list[CredentialVaultEntryResponse]:
    """Return credential metadata visible to the caller."""
    context = _context_from_workflow(workflow_id)
    credentials = vault.list_credentials(context=context)
    return [_credential_to_response(metadata) for metadata in credentials]


@_http_router.post(
    "/credentials",
    response_model=CredentialVaultEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_credential(
    request: CredentialCreateRequest,
    vault: VaultDep,
) -> CredentialVaultEntryResponse:
    """Persist a new credential in the vault."""
    scope = _scope_from_access(request.access, request.workflow_id)
    try:
        metadata = vault.create_credential(
            name=request.name,
            provider=request.provider,
            scopes=request.scopes,
            secret=request.secret,
            actor=request.actor,
            scope=scope,
            kind=request.kind,
        )
    except DuplicateCredentialNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    response = _credential_to_response(metadata)
    if request.access != response.access:
        response = response.model_copy(update={"access": request.access})
    return response


@_http_router.delete(
    "/credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_credential(
    credential_id: UUID,
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> Response:
    """Delete a credential."""
    context = _context_from_workflow(workflow_id)
    try:
        vault.delete_credential(credential_id, context=context)
    except CredentialNotFoundError as exc:
        _raise_not_found("Credential not found", exc)
    except WorkflowScopeError as exc:
        _raise_scope_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@_http_router.get(
    "/credentials/templates",
    response_model=list[CredentialTemplateResponse],
)
def list_credential_templates(
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> list[CredentialTemplateResponse]:
    """List credential templates visible to the caller."""
    context = _context_from_workflow(workflow_id)
    templates = vault.list_templates(context=context)
    return [_template_to_response(template) for template in templates]


@_http_router.post(
    "/credentials/templates",
    response_model=CredentialTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_credential_template(
    request: CredentialTemplateCreateRequest, vault: VaultDep
) -> CredentialTemplateResponse:
    """Create a new credential template."""
    scope = _build_scope(request.scope)
    policy = _build_policy(request.issuance_policy)
    template = vault.create_template(
        name=request.name,
        provider=request.provider,
        scopes=request.scopes,
        actor=request.actor,
        description=request.description,
        scope=scope,
        kind=request.kind,
        issuance_policy=policy,
    )
    return _template_to_response(template)


@_http_router.get(
    "/credentials/templates/{template_id}",
    response_model=CredentialTemplateResponse,
)
def get_credential_template(
    template_id: UUID,
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> CredentialTemplateResponse:
    """Return a single credential template."""
    context = _context_from_workflow(workflow_id)
    try:
        template = vault.get_template(template_id=template_id, context=context)
        return _template_to_response(template)
    except CredentialTemplateNotFoundError as exc:
        _raise_not_found("Credential template not found", exc)
    except WorkflowScopeError as exc:
        _raise_scope_error(exc)


@_http_router.patch(
    "/credentials/templates/{template_id}",
    response_model=CredentialTemplateResponse,
)
def update_credential_template(
    template_id: UUID,
    request: CredentialTemplateUpdateRequest,
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> CredentialTemplateResponse:
    """Update credential template metadata."""
    context = _context_from_workflow(workflow_id)
    scope = _build_scope(request.scope)
    policy = _build_policy(request.issuance_policy)
    kind: CredentialKind | None = request.kind
    try:
        template = vault.update_template(
            template_id,
            actor=request.actor,
            name=request.name,
            scopes=request.scopes,
            description=request.description,
            scope=scope,
            kind=kind,
            issuance_policy=policy,
            context=context,
        )
        return _template_to_response(template)
    except CredentialTemplateNotFoundError as exc:
        _raise_not_found("Credential template not found", exc)
    except WorkflowScopeError as exc:
        _raise_scope_error(exc)


@_http_router.delete(
    "/credentials/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_credential_template(
    template_id: UUID,
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> Response:
    """Delete a credential template."""
    context = _context_from_workflow(workflow_id)
    try:
        vault.delete_template(template_id, context=context)
    except CredentialTemplateNotFoundError as exc:
        _raise_not_found("Credential template not found", exc)
    except WorkflowScopeError as exc:
        _raise_scope_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@_http_router.post(
    "/credentials/templates/{template_id}/issue",
    response_model=CredentialIssuanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def issue_credential_from_template(
    template_id: UUID,
    request: CredentialIssuanceRequest,
    service: CredentialServiceDep,
) -> CredentialIssuanceResponse:
    """Issue a credential based on a stored template."""
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credential service is not configured.",
        )

    context = _context_from_workflow(request.workflow_id)
    tokens = _build_oauth_tokens(request.oauth_tokens)
    try:
        metadata = service.issue_from_template(
            template_id=template_id,
            secret=request.secret,
            actor=request.actor,
            name=request.name,
            scopes=request.scopes,
            context=context,
            oauth_tokens=tokens,
        )
    except CredentialTemplateNotFoundError as exc:
        _raise_not_found("Credential template not found", exc)
    except WorkflowScopeError as exc:
        _raise_scope_error(exc)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return CredentialIssuanceResponse(
        credential_id=str(metadata.id),
        name=metadata.name,
        provider=metadata.provider,
        kind=metadata.kind,
        template_id=str(metadata.template_id) if metadata.template_id else None,
        created_at=metadata.created_at,
        updated_at=metadata.updated_at,
    )


@_http_router.get(
    "/credentials/governance-alerts",
    response_model=list[GovernanceAlertResponse],
)
def list_governance_alerts(
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
    include_acknowledged: IncludeAcknowledgedQuery = False,
) -> list[GovernanceAlertResponse]:
    """List governance alerts for the caller."""
    context = _context_from_workflow(workflow_id)
    alerts = vault.list_alerts(
        context=context, include_acknowledged=include_acknowledged
    )
    return [_alert_to_response(alert) for alert in alerts]


@_http_router.post(
    "/credentials/governance-alerts/{alert_id}/acknowledge",
    response_model=GovernanceAlertResponse,
)
def acknowledge_governance_alert(
    alert_id: UUID,
    request: AlertAcknowledgeRequest,
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> GovernanceAlertResponse:
    """Acknowledge an outstanding governance alert."""
    context = _context_from_workflow(workflow_id)
    try:
        alert = vault.acknowledge_alert(alert_id, actor=request.actor, context=context)
        return _alert_to_response(alert)
    except GovernanceAlertNotFoundError as exc:
        _raise_not_found("Governance alert not found", exc)
    except WorkflowScopeError as exc:
        _raise_scope_error(exc)


@_http_router.get(
    "/workflows/{workflow_id}/credentials/health",
    response_model=CredentialHealthResponse,
)
async def get_workflow_credential_health(
    workflow_id: UUID,
    repository: RepositoryDep,
    service: CredentialServiceDep,
) -> CredentialHealthResponse:
    try:
        await repository.get_workflow(workflow_id)
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credential health service is not configured.",
        )

    report = service.get_report(workflow_id)
    if report is None:
        return CredentialHealthResponse(
            workflow_id=str(workflow_id),
            status=CredentialHealthStatus.UNKNOWN,
            checked_at=None,
            credentials=[],
        )
    return _health_report_to_response(report)


@_http_router.post(
    "/workflows/{workflow_id}/credentials/validate",
    response_model=CredentialHealthResponse,
)
async def validate_workflow_credentials(
    workflow_id: UUID,
    request: CredentialValidationRequest,
    repository: RepositoryDep,
    service: CredentialServiceDep,
) -> CredentialHealthResponse:
    try:
        await repository.get_workflow(workflow_id)
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credential health service is not configured.",
        )

    report = await service.ensure_workflow_health(workflow_id, actor=request.actor)
    if not report.is_healthy:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Credentials failed validation.",
                "failures": report.failures,
            },
        )
    return _health_report_to_response(report)


@_http_router.get(
    "/workflows/{workflow_id}/runs",
    response_model=list[WorkflowRun],
)
async def list_workflow_runs(
    workflow_id: UUID,
    repository: RepositoryDep,
) -> list[WorkflowRun]:
    """List runs for a given workflow."""
    try:
        return await repository.list_runs_for_workflow(workflow_id)
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)


@_http_router.get(
    "/workflows/{workflow_id}/executions",
    response_model=list[RunHistoryResponse],
)
async def list_workflow_execution_histories(
    workflow_id: UUID,
    history_store: HistoryStoreDep,
    limit: int = Query(50, ge=1, le=200),
) -> list[RunHistoryResponse]:
    """Return execution histories recorded for the workflow."""
    records = await history_store.list_histories(str(workflow_id), limit=limit)
    return [_history_to_response(record) for record in records]


@_http_router.get("/runs/{run_id}", response_model=WorkflowRun)
async def get_workflow_run(
    run_id: UUID,
    repository: RepositoryDep,
) -> WorkflowRun:
    """Retrieve a single workflow run."""
    try:
        return await repository.get_run(run_id)
    except WorkflowRunNotFoundError as exc:
        _raise_not_found("Workflow run not found", exc)


@_http_router.get(
    "/executions/{execution_id}/history",
    response_model=RunHistoryResponse,
)
async def get_execution_history(
    execution_id: str, history_store: HistoryStoreDep
) -> RunHistoryResponse:
    """Return the recorded execution history for a workflow run."""
    try:
        record = await history_store.get_history(execution_id)
    except RunHistoryNotFoundError as exc:
        _raise_not_found("Execution history not found", exc)
    return _history_to_response(record)


@_http_router.post(
    "/executions/{execution_id}/replay",
    response_model=RunHistoryResponse,
)
async def replay_execution(
    execution_id: str,
    request: RunReplayRequest,
    history_store: HistoryStoreDep,
) -> RunHistoryResponse:
    """Return a sliced view of the execution history for replay clients."""
    try:
        record = await history_store.get_history(execution_id)
    except RunHistoryNotFoundError as exc:
        _raise_not_found("Execution history not found", exc)
    return _history_to_response(record, from_step=request.from_step)


@_http_router.post("/runs/{run_id}/start", response_model=WorkflowRun)
async def mark_run_started(
    run_id: UUID,
    request: RunActionRequest,
    repository: RepositoryDep,
) -> WorkflowRun:
    """Transition a run into the running state."""
    try:
        return await repository.mark_run_started(run_id, actor=request.actor)
    except WorkflowRunNotFoundError as exc:
        _raise_not_found("Workflow run not found", exc)
    except ValueError as exc:
        _raise_conflict(str(exc), exc)


@_http_router.post("/runs/{run_id}/succeed", response_model=WorkflowRun)
async def mark_run_succeeded(
    run_id: UUID,
    request: RunSucceedRequest,
    repository: RepositoryDep,
) -> WorkflowRun:
    """Mark a workflow run as successful."""
    try:
        return await repository.mark_run_succeeded(
            run_id,
            actor=request.actor,
            output=request.output,
        )
    except WorkflowRunNotFoundError as exc:
        _raise_not_found("Workflow run not found", exc)
    except ValueError as exc:
        _raise_conflict(str(exc), exc)


@_http_router.post("/runs/{run_id}/fail", response_model=WorkflowRun)
async def mark_run_failed(
    run_id: UUID,
    request: RunFailRequest,
    repository: RepositoryDep,
) -> WorkflowRun:
    """Mark a workflow run as failed."""
    try:
        return await repository.mark_run_failed(
            run_id,
            actor=request.actor,
            error=request.error,
        )
    except WorkflowRunNotFoundError as exc:
        _raise_not_found("Workflow run not found", exc)
    except ValueError as exc:
        _raise_conflict(str(exc), exc)


@_http_router.post("/runs/{run_id}/cancel", response_model=WorkflowRun)
async def mark_run_cancelled(
    run_id: UUID,
    request: RunCancelRequest,
    repository: RepositoryDep,
) -> WorkflowRun:
    """Cancel a workflow run."""
    try:
        return await repository.mark_run_cancelled(
            run_id,
            actor=request.actor,
            reason=request.reason,
        )
    except WorkflowRunNotFoundError as exc:
        _raise_not_found("Workflow run not found", exc)
    except ValueError as exc:
        _raise_conflict(str(exc), exc)


@_http_router.put(
    "/workflows/{workflow_id}/triggers/webhook/config",
    response_model=WebhookTriggerConfig,
)
async def configure_webhook_trigger(
    workflow_id: UUID,
    request: WebhookTriggerConfig,
    repository: RepositoryDep,
) -> WebhookTriggerConfig:
    """Persist webhook trigger configuration for the workflow."""
    try:
        return await repository.configure_webhook_trigger(workflow_id, request)
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)


@_http_router.get(
    "/workflows/{workflow_id}/triggers/webhook/config",
    response_model=WebhookTriggerConfig,
)
async def get_webhook_trigger_config(
    workflow_id: UUID,
    repository: RepositoryDep,
) -> WebhookTriggerConfig:
    """Return the configured webhook trigger definition."""
    try:
        return await repository.get_webhook_trigger_config(workflow_id)
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)


@_http_router.api_route(
    "/workflows/{workflow_id}/triggers/webhook",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    response_model=WorkflowRun,
    status_code=status.HTTP_202_ACCEPTED,
)
async def invoke_webhook_trigger(
    workflow_id: UUID,
    request: Request,
    repository: RepositoryDep,
) -> WorkflowRun:
    """Validate inbound webhook data and enqueue a workflow run."""
    try:
        raw_body = await request.body()
    except Exception as exc:  # pragma: no cover - FastAPI handles body read
        raise HTTPException(
            status_code=400,
            detail="Failed to read request body",
        ) from exc

    payload: Any
    if raw_body:
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = raw_body
    else:
        payload = {}

    headers = {key: value for key, value in request.headers.items()}
    query_params = {key: value for key, value in request.query_params.items()}
    source_ip = request.client.host if request.client else None

    try:
        return await repository.handle_webhook_trigger(
            workflow_id,
            method=request.method,
            headers=headers,
            query_params=query_params,
            payload=payload,
            source_ip=source_ip,
        )
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)
    except WorkflowVersionNotFoundError as exc:
        _raise_not_found("Workflow version not found", exc)
    except WebhookValidationError as exc:
        _raise_webhook_error(exc)
    except CredentialHealthError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(exc), "failures": exc.report.failures},
        ) from exc


@_http_router.put(
    "/workflows/{workflow_id}/triggers/cron/config",
    response_model=CronTriggerConfig,
)
async def configure_cron_trigger(
    workflow_id: UUID,
    request: CronTriggerConfig,
    repository: RepositoryDep,
) -> CronTriggerConfig:
    """Persist cron trigger configuration for the workflow."""
    try:
        return await repository.configure_cron_trigger(workflow_id, request)
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)


@_http_router.get(
    "/workflows/{workflow_id}/triggers/cron/config",
    response_model=CronTriggerConfig,
)
async def get_cron_trigger_config(
    workflow_id: UUID,
    repository: RepositoryDep,
) -> CronTriggerConfig:
    """Return the configured cron trigger definition."""
    try:
        return await repository.get_cron_trigger_config(workflow_id)
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)


@_http_router.post(
    "/triggers/cron/dispatch",
    response_model=list[WorkflowRun],
)
async def dispatch_cron_triggers(
    repository: RepositoryDep,
    request: CronDispatchRequest | None = None,
) -> list[WorkflowRun]:
    """Evaluate cron schedules and enqueue any due runs."""
    now = request.now if request else None
    try:
        return await repository.dispatch_due_cron_runs(now=now)
    except CredentialHealthError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(exc), "failures": exc.report.failures},
        ) from exc


@_http_router.post(
    "/triggers/manual/dispatch",
    response_model=list[WorkflowRun],
)
async def dispatch_manual_runs(
    request: ManualDispatchRequest, repository: RepositoryDep
) -> list[WorkflowRun]:
    """Dispatch one or more manual workflow runs."""
    try:
        return await repository.dispatch_manual_runs(request)
    except WorkflowNotFoundError as exc:
        _raise_not_found("Workflow not found", exc)
    except WorkflowVersionNotFoundError as exc:
        _raise_not_found("Workflow version not found", exc)
    except CredentialHealthError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(exc), "failures": exc.report.failures},
        ) from exc


@_http_router.post(
    "/nodes/execute",
    response_model=NodeExecutionResponse,
)
async def execute_node(
    request: NodeExecutionRequest,
) -> NodeExecutionResponse:
    """Execute a single node in isolation for testing/preview purposes.

    This endpoint allows executing individual nodes without creating a full workflow,
    useful for testing node configurations in the Node Inspector UI.

    Args:
        request: Node execution request containing node_config, inputs, and optional
                workflow_id for credential context

    Returns:
        NodeExecutionResponse with status, result, and optional error message

    Raises:
        HTTPException: 400 if node type is missing or unknown
        HTTPException: 500 if node execution fails
    """
    from orcheo.nodes.registry import registry

    node_config = request.node_config
    inputs = request.inputs
    # workflow_id = request.workflow_id  # Reserved for future credential context

    # Validate node configuration
    node_type = node_config.get("type")
    if not node_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Node configuration must include a 'type' field",
        )

    # Get node class from registry
    node_class = registry.get_node(str(node_type))
    if node_class is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown node type: {node_type}",
        )

    try:
        # Extract node parameters (everything except 'type')
        node_params = {k: v for k, v in node_config.items() if k != "type"}

        vault = get_vault()
        context = _context_from_workflow(request.workflow_id)
        resolver = CredentialResolver(vault, context=context)

        with credential_resolution(resolver):
            # Instantiate the node
            node_instance = node_class(**node_params)

            # Create minimal state for execution
            state: State = {
                "messages": [],
                "results": {},
                "inputs": inputs,
            }

            # Create config with optional workflow context for credentials
            config: RunnableConfig = {"configurable": {"thread_id": str(uuid.uuid4())}}

            # Execute the node
            result = await node_instance(state, config)

        # Extract the actual result based on node type
        # AINode wraps in messages, TaskNode wraps in results
        node_name = node_params.get("name", "node")
        node_result = None

        if "results" in result and node_name in result["results"]:
            node_result = result["results"][node_name]
        elif "messages" in result:  # pragma: no cover
            node_result = result["messages"]

        return NodeExecutionResponse(
            status="success",
            result=node_result,
        )

    except Exception as exc:
        logger.exception("Node execution failed: %s", exc)
        return NodeExecutionResponse(
            status="error",
            error=str(exc),
        )


def create_app(
    repository: WorkflowRepository | None = None,
    *,
    history_store: RunHistoryStore | None = None,
    credential_service: OAuthCredentialService | None = None,
) -> FastAPI:
    """Instantiate and configure the FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        """Manage application lifespan with startup and shutdown logic."""
        # Startup
        try:
            get_chatkit_server()
            await _ensure_chatkit_cleanup_task()
        except HTTPException:
            pass
        yield
        # Shutdown
        await _cancel_chatkit_cleanup_task()

    application = FastAPI(lifespan=lifespan)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if repository is not None:
        application.dependency_overrides[get_repository] = lambda: repository
    if history_store is not None:
        application.dependency_overrides[get_history_store] = lambda: history_store
        _history_store_ref["store"] = history_store
    if credential_service is not None:
        _credential_service_ref["service"] = credential_service
        _vault_ref["vault"] = getattr(credential_service, "_vault", None)
        application.dependency_overrides[get_credential_service] = (
            lambda: credential_service
        )
    elif repository is not None:
        inferred_service = getattr(repository, "_credential_service", None)
        if inferred_service is not None:
            _credential_service_ref["service"] = inferred_service
            application.dependency_overrides[get_credential_service] = (
                lambda: inferred_service
            )

    application.include_router(_http_router)
    application.include_router(_ws_router)

    return application


app = create_app()


__all__ = [
    "app",
    "create_app",
    "execute_workflow",
    "get_repository",
    "workflow_websocket",
]


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
