"""FastAPI application entrypoint for the Orcheo backend service."""

from __future__ import annotations
import asyncio
import json
import logging
import secrets
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any, NoReturn, TypeVar, cast
from uuid import UUID
from chatkit.server import NonStreamingResult, StreamingResult
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
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.datastructures import Headers, MutableHeaders
from orcheo.config import get_settings
from orcheo.graph.builder import build_graph
from orcheo.graph.ingestion import (
    LANGGRAPH_SCRIPT_FORMAT,
    ScriptIngestionError,
    ingest_langgraph_script,
)
from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialIssuancePolicy,
    CredentialKind,
    CredentialScope,
    CredentialTemplate,
    OAuthTokenSecrets,
    SecretGovernanceAlert,
)
from orcheo.models.workflow import Workflow, WorkflowRun, WorkflowVersion
from orcheo.persistence import create_checkpointer
from orcheo.triggers.cron import CronTriggerConfig
from orcheo.triggers.manual import ManualDispatchRequest
from orcheo.triggers.webhook import WebhookTriggerConfig, WebhookValidationError
from orcheo.vault import (
    BaseCredentialVault,
    CredentialTemplateNotFoundError,
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
from orcheo_backend.app.chatkit_server import OrcheoChatKitServer
from orcheo_backend.app.history import (
    InMemoryRunHistoryStore,
    RunHistoryNotFoundError,
    RunHistoryRecord,
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
    CronDispatchRequest,
    GovernanceAlertResponse,
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
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

_ws_router = APIRouter()
_http_router = APIRouter(prefix="/api")
_repository: WorkflowRepository
_history_store_ref: dict[str, InMemoryRunHistoryStore] = {
    "store": InMemoryRunHistoryStore()
}
_credential_service_ref: dict[str, OAuthCredentialService | None] = {"service": None}
_vault_ref: dict[str, BaseCredentialVault | None] = {"vault": None}
_chatkit_server_ref: dict[str, OrcheoChatKitServer | None] = {"server": None}

T = TypeVar("T")


def _get_chatkit_server() -> OrcheoChatKitServer:
    server = _chatkit_server_ref["server"]
    if server is None:
        server = OrcheoChatKitServer()
        _chatkit_server_ref["server"] = server
    return server


def _settings_value(
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


def _create_vault(settings: Dynaconf) -> BaseCredentialVault:
    backend = cast(
        str,
        _settings_value(
            settings,
            attr_path="vault.backend",
            env_key="VAULT_BACKEND",
            default="inmemory",
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
    encryption_key = key or secrets.token_hex(32)
    cipher = AesGcmCredentialCipher(key=encryption_key)
    if backend == "inmemory":
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
        return SqliteWorkflowRepository(sqlite_path, credential_service=service)
    if backend == "inmemory":
        return InMemoryWorkflowRepository(credential_service=service)
    msg = "Unsupported repository backend configured."
    raise ValueError(msg)


_repository = _create_repository()


def get_repository() -> WorkflowRepository:
    """Return the singleton workflow repository instance."""
    return _repository


RepositoryDep = Annotated[WorkflowRepository, Depends(get_repository)]


def get_history_store() -> InMemoryRunHistoryStore:
    """Return the singleton execution history store."""
    return _history_store_ref["store"]


HistoryStoreDep = Annotated[InMemoryRunHistoryStore, Depends(get_history_store)]


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
    logger.info("Initial inputs: %s", inputs)

    settings = get_settings()
    history_store = get_history_store()
    await history_store.start_run(
        workflow_id=workflow_id, execution_id=execution_id, inputs=inputs
    )

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
        logger.info("Initial state: %s", state)

        # Run graph with streaming
        config = {"configurable": {"thread_id": execution_id}}
        try:
            async for step in compiled_graph.astream(
                state,
                config=config,  # type: ignore[arg-type]
                stream_mode="updates",
            ):  # pragma: no cover
                await history_store.append_step(execution_id, step)
                try:
                    await websocket.send_json(step)
                except Exception as exc:  # pragma: no cover
                    logger.error("Error processing messages: %s", exc)
                    raise
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


def _build_chatkit_response_kwargs(
    result: StreamingResult | NonStreamingResult,
) -> dict[str, Any]:
    """Extract shared response keyword arguments from ChatKit results."""
    status_code = getattr(result, "status", None)
    headers: Any = getattr(result, "headers", None)

    normalized_headers: Any | None = None
    if headers:
        if isinstance(headers, Headers | MutableHeaders):
            normalized_headers = dict(headers.items())
        elif isinstance(headers, Mapping):
            normalized_headers = dict(headers)
        elif isinstance(headers, Sequence) and not isinstance(
            headers, str | bytes | bytearray
        ):
            normalized_headers = list(headers)
        else:
            normalized_headers = headers

    response_kwargs: dict[str, Any] = {}
    if status_code is not None:
        response_kwargs["status_code"] = status_code
    if normalized_headers is not None:
        response_kwargs["headers"] = normalized_headers

    return response_kwargs


@_http_router.post("/chatkit")
async def handle_chatkit(request: Request) -> Response:
    """Process ChatKit client requests and stream responses."""
    server = _get_chatkit_server()
    payload = await request.body()
    result = await server.process(payload, {"request": request})
    response_kwargs = _build_chatkit_response_kwargs(result)
    if isinstance(result, StreamingResult):
        return StreamingResponse(
            result, media_type="text/event-stream", **response_kwargs
        )
    if isinstance(result, NonStreamingResult):
        return Response(
            content=result.json,
            media_type="application/json",
            **response_kwargs,
        )
    return JSONResponse({"error": "Unexpected ChatKit response"}, status_code=500)


@_http_router.get("/workflows", response_model=list[Workflow])
async def list_workflows(
    repository: RepositoryDep,
) -> list[Workflow]:
    """Return all registered workflows."""
    return await repository.list_workflows()


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


def create_app(
    repository: WorkflowRepository | None = None,
    *,
    history_store: InMemoryRunHistoryStore | None = None,
    credential_service: OAuthCredentialService | None = None,
) -> FastAPI:
    """Instantiate and configure the FastAPI application."""
    application = FastAPI()

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
