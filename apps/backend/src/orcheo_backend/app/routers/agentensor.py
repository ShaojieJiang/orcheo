"""Agentensor checkpoint APIs."""

from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Query
from orcheo.agentensor.checkpoints import AgentensorCheckpointNotFoundError
from orcheo_backend.app.dependencies import CheckpointStoreDep
from orcheo_backend.app.errors import raise_not_found
from orcheo_backend.app.schemas.agentensor import AgentensorCheckpointResponse


router = APIRouter()


@router.get(
    "/workflows/{workflow_id}/agentensor/checkpoints",
    response_model=list[AgentensorCheckpointResponse],
)
async def list_agentensor_checkpoints(
    workflow_id: UUID,
    store: CheckpointStoreDep,
    limit: int = Query(20, ge=1, le=200),
) -> list[AgentensorCheckpointResponse]:
    """List checkpoints for the specified workflow."""
    checkpoints = await store.list_checkpoints(str(workflow_id), limit=limit)
    return [AgentensorCheckpointResponse.from_domain(item) for item in checkpoints]


@router.get(
    "/workflows/{workflow_id}/agentensor/checkpoints/{checkpoint_id}",
    response_model=AgentensorCheckpointResponse,
)
async def get_agentensor_checkpoint(
    workflow_id: UUID,
    checkpoint_id: str,
    store: CheckpointStoreDep,
) -> AgentensorCheckpointResponse:
    """Return a single checkpoint for the workflow."""
    try:
        checkpoint = await store.get_checkpoint(checkpoint_id)
    except AgentensorCheckpointNotFoundError as exc:
        raise_not_found("Checkpoint not found", exc)
    if checkpoint.workflow_id != str(workflow_id):
        raise_not_found("Checkpoint not found", AgentensorCheckpointNotFoundError(""))
    return AgentensorCheckpointResponse.from_domain(checkpoint)


__all__ = ["router"]
