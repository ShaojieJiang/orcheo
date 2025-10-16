"""FastAPI application entrypoint for the Orcheo backend service."""

from __future__ import annotations
import asyncio
import json
import logging
import uuid
from typing import Annotated, Any, NoReturn
from uuid import UUID
from dotenv import load_dotenv
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from orcheo.config import get_settings
from orcheo.graph.builder import build_graph
from orcheo.graph.ingestion import (
    LANGGRAPH_SCRIPT_FORMAT,
    ScriptIngestionError,
    ingest_langgraph_script,
)
from orcheo.models.workflow import Workflow, WorkflowRun, WorkflowVersion
from orcheo.persistence import create_checkpointer
from orcheo.triggers.cron import CronTriggerConfig
from orcheo.triggers.manual import ManualDispatchRequest
from orcheo.triggers.webhook import WebhookTriggerConfig, WebhookValidationError
from orcheo_backend.app.history import (
    InMemoryRunHistoryStore,
    RunHistoryNotFoundError,
    RunHistoryRecord,
)
from orcheo_backend.app.repository import (
    InMemoryWorkflowRepository,
    WorkflowNotFoundError,
    WorkflowRunNotFoundError,
    WorkflowVersionNotFoundError,
)
from orcheo_backend.app.schemas import (
    CronDispatchRequest,
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
_repository = InMemoryWorkflowRepository()
_history_store_ref: dict[str, InMemoryRunHistoryStore] = {
    "store": InMemoryRunHistoryStore()
}


def get_repository() -> InMemoryWorkflowRepository:
    """Return the singleton workflow repository instance."""
    return _repository


RepositoryDep = Annotated[InMemoryWorkflowRepository, Depends(get_repository)]


def get_history_store() -> InMemoryRunHistoryStore:
    """Return the singleton execution history store."""
    return _history_store_ref["store"]


HistoryStoreDep = Annotated[InMemoryRunHistoryStore, Depends(get_history_store)]


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
    return await repository.dispatch_due_cron_runs(now=now)


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


def create_app(
    repository: InMemoryWorkflowRepository | None = None,
    *,
    history_store: InMemoryRunHistoryStore | None = None,
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
