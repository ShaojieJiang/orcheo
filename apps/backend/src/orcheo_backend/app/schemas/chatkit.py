"""ChatKit-related request/response schemas."""

from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ChatKitSessionRequest(BaseModel):
    """Request payload for retrieving a ChatKit client secret."""

    current_client_secret: str | None = Field(default=None, alias="currentClientSecret")
    workflow_id: UUID | None = Field(default=None, alias="workflowId")
    workflow_label: str | None = Field(default=None, alias="workflowLabel")
    metadata: dict[str, Any] = Field(default_factory=dict)
    user: dict[str, Any] | None = None
    assistant: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class ChatKitSessionResponse(BaseModel):
    """Response payload describing a ChatKit client session."""

    client_secret: str = Field(alias="client_secret")
    expires_at: datetime | None = None

    model_config = ConfigDict(populate_by_name=True)


class ChatKitWorkflowTriggerRequest(BaseModel):
    """Payload for triggering a workflow run from ChatKit."""

    message: str
    actor: str = Field(default="chatkit")
    client_thread_id: str | None = Field(default=None, alias="client_thread_id")
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)
