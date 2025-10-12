"""Pydantic request schemas for the FastAPI service."""

from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


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


class WorkflowVersionDiffResponse(BaseModel):
    """Response payload for workflow version diffs."""

    base_version: int
    target_version: int
    diff: list[str]


class CronDispatchRequest(BaseModel):
    """Request body for dispatching cron triggers."""

    now: datetime | None = None


class RetryPolicyConfigBase(BaseModel):
    """Shared fields for retry policy configuration payloads."""

    max_attempts: int = Field(
        default=3,
        ge=1,
        description="Total attempts including the initial execution.",
    )
    initial_delay_seconds: float = Field(
        default=30.0,
        ge=0.0,
        description="Delay applied before the first retry attempt.",
    )
    backoff_factor: float = Field(
        default=2.0,
        ge=1.0,
        description="Multiplier applied to the delay after each failed attempt.",
    )
    max_delay_seconds: float | None = Field(
        default=300.0,
        ge=0.0,
        description="Optional ceiling for computed retry delays.",
    )
    jitter_factor: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description=(
            "Percentage of jitter applied to each delay as a fraction of the "
            "computed delay."
        ),
    )


class RetryPolicyConfigRequest(RetryPolicyConfigBase):
    """Payload for configuring retry policy settings."""


class RetryPolicyConfigResponse(RetryPolicyConfigBase):
    """Response body containing retry policy configuration."""
