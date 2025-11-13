"""Workflow run management routes."""

from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status
from orcheo.models.workflow import WorkflowRun
from orcheo.vault.oauth import CredentialHealthError
from orcheo_backend.app.dependencies import (
    CredentialServiceDep,
    HistoryStoreDep,
    RepositoryDep,
)
from orcheo_backend.app.errors import raise_conflict, raise_not_found
from orcheo_backend.app.history import RunHistoryNotFoundError
from orcheo_backend.app.history_utils import history_to_response, trace_to_response
from orcheo_backend.app.repository import (
    WorkflowNotFoundError,
    WorkflowRunNotFoundError,
    WorkflowVersionNotFoundError,
)
from orcheo_backend.app.schemas.runs import (
    RunActionRequest,
    RunCancelRequest,
    RunFailRequest,
    RunHistoryResponse,
    RunReplayRequest,
    RunSucceedRequest,
    RunTraceResponse,
)
from orcheo_backend.app.schemas.workflows import WorkflowRunCreateRequest


router = APIRouter()


@router.post(
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
        raise_not_found("Workflow not found", exc)
    except WorkflowVersionNotFoundError as exc:
        raise_not_found("Workflow version not found", exc)
    except CredentialHealthError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": str(exc), "failures": exc.report.failures},
        ) from exc


@router.get(
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
        raise_not_found("Workflow not found", exc)


@router.get("/runs/{run_id}", response_model=WorkflowRun)
async def get_workflow_run(
    run_id: UUID,
    repository: RepositoryDep,
) -> WorkflowRun:
    """Retrieve a single workflow run."""
    try:
        return await repository.get_run(run_id)
    except WorkflowRunNotFoundError as exc:
        raise_not_found("Workflow run not found", exc)


@router.post("/runs/{run_id}/start", response_model=WorkflowRun)
async def mark_run_started(
    run_id: UUID,
    request: RunActionRequest,
    repository: RepositoryDep,
) -> WorkflowRun:
    """Transition a run into the running state."""
    try:
        return await repository.mark_run_started(run_id, actor=request.actor)
    except WorkflowRunNotFoundError as exc:
        raise_not_found("Workflow run not found", exc)
    except ValueError as exc:
        raise_conflict(str(exc), exc)


@router.post("/runs/{run_id}/succeed", response_model=WorkflowRun)
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
        raise_not_found("Workflow run not found", exc)
    except ValueError as exc:
        raise_conflict(str(exc), exc)


@router.post("/runs/{run_id}/fail", response_model=WorkflowRun)
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
        raise_not_found("Workflow run not found", exc)
    except ValueError as exc:
        raise_conflict(str(exc), exc)


@router.post("/runs/{run_id}/cancel", response_model=WorkflowRun)
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
        raise_not_found("Workflow run not found", exc)
    except ValueError as exc:
        raise_conflict(str(exc), exc)


@router.get(
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
    return [history_to_response(record) for record in records]


@router.get(
    "/executions/{execution_id}/history",
    response_model=RunHistoryResponse,
)
async def get_execution_history(
    execution_id: str,
    history_store: HistoryStoreDep,
) -> RunHistoryResponse:
    """Return the recorded execution history for a workflow run."""
    try:
        record = await history_store.get_history(execution_id)
    except RunHistoryNotFoundError as exc:
        raise_not_found("Execution history not found", exc)
    return history_to_response(record)


@router.get(
    "/executions/{execution_id}/trace",
    response_model=RunTraceResponse,
)
async def get_execution_trace(
    execution_id: str,
    history_store: HistoryStoreDep,
    cursor: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> RunTraceResponse:
    """Return serialized trace metadata for the requested execution."""
    try:
        record = await history_store.get_history(execution_id)
    except RunHistoryNotFoundError as exc:
        raise_not_found("Execution history not found", exc)
    page_cursor = cursor or 0
    return trace_to_response(record, cursor=page_cursor, limit=limit)


@router.post(
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
        raise_not_found("Execution history not found", exc)
    return history_to_response(record, from_step=request.from_step)


__all__ = ["router"]
