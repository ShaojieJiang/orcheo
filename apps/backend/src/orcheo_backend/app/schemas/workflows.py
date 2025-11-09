"""Workflow-related request/response schemas."""

from __future__ import annotations
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from orcheo.graph.ingestion import DEFAULT_SCRIPT_SIZE_LIMIT
from orcheo.models.workflow import Workflow


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


class WorkflowVersionDiffResponse(BaseModel):
    """Response payload for workflow version diffs."""

    base_version: int
    target_version: int
    diff: list[str]


class WorkflowPublishRequest(BaseModel):
    """Payload for publishing a workflow."""

    require_login: bool = False
    actor: str = Field(default="system")


class WorkflowPublishRevokeRequest(BaseModel):
    """Payload for revoking workflow publication."""

    actor: str = Field(default="system")


class WorkflowPublishResponse(BaseModel):
    """Response payload for publish actions."""

    workflow: Workflow
    message: str | None = None
