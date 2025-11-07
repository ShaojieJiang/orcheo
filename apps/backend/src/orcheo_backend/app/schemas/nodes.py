"""Node execution schemas."""

from __future__ import annotations
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


class NodeExecutionRequest(BaseModel):
    """Request payload for executing a single node in isolation."""

    node_config: dict[str, Any]
    inputs: dict[str, Any] = Field(default_factory=dict)
    workflow_id: UUID | None = None


class NodeExecutionResponse(BaseModel):
    """Response payload for single-node execution."""

    status: str
    result: Any | None = None
    error: str | None = None
