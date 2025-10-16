"""Pydantic request schemas for the FastAPI service."""

from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from orcheo.graph.ingestion import DEFAULT_SCRIPT_SIZE_LIMIT


class WorkflowCreateRequest(BaseModel):
    """Payload for creating a new workflow."""

    name: str
    slug: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    actor: str = Field(default="system")


class WorkflowUpdateRequest(BaseModel):
    """Payload for updating an existing workflow."""

    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    is_archived: bool | None = None
    actor: str = Field(default="system")


class WorkflowVersionCreateRequest(BaseModel):
    """Payload for creating a workflow version."""

    graph: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    created_by: str


class WorkflowVersionIngestRequest(BaseModel):
    """Payload for ingesting a LangGraph Python script."""

    script: str
    entrypoint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    created_by: str

    @field_validator("script")
    @classmethod
    def _enforce_script_size(cls, value: str) -> str:
        size = len(value.encode("utf-8"))
        if size > DEFAULT_SCRIPT_SIZE_LIMIT:
            msg = (
                "LangGraph script exceeds the maximum allowed size of "
                f"{DEFAULT_SCRIPT_SIZE_LIMIT} bytes"
            )
            raise ValueError(msg)
        return value


class WorkflowRunCreateRequest(BaseModel):
    """Payload for creating a new workflow execution run."""

    workflow_version_id: UUID
    triggered_by: str
    input_payload: dict[str, Any] = Field(default_factory=dict)


class RunActionRequest(BaseModel):
    """Base payload for run lifecycle transitions."""

    actor: str


class RunSucceedRequest(RunActionRequest):
    """Payload for marking a run as succeeded."""

    output: dict[str, Any] | None = None


class RunFailRequest(RunActionRequest):
    """Payload for marking a run as failed."""

    error: str


class RunCancelRequest(RunActionRequest):
    """Payload for cancelling a run."""

    reason: str | None = None


class RunHistoryStepResponse(BaseModel):
    """Response payload describing a single run history step."""

    index: int
    at: datetime
    payload: dict[str, Any]


class RunHistoryResponse(BaseModel):
    """Execution history response returned by the API."""

    execution_id: str
    workflow_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    steps: list[RunHistoryStepResponse] = Field(default_factory=list)


class RunReplayRequest(BaseModel):
    """Request body for replaying a run from a given step index."""

    from_step: int = Field(default=0, ge=0)


class WorkflowVersionDiffResponse(BaseModel):
    """Response payload for workflow version diffs."""

    base_version: int
    target_version: int
    diff: list[str]


class CronDispatchRequest(BaseModel):
    """Request body for dispatching cron triggers."""

    now: datetime | None = None
