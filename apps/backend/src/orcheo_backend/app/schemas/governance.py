"""Governance alert schemas."""

from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field
from orcheo.models import GovernanceAlertKind, SecretGovernanceAlertSeverity


class GovernanceAlertResponse(BaseModel):
    """Response payload describing a governance alert."""

    id: str
    kind: GovernanceAlertKind
    severity: SecretGovernanceAlertSeverity
    message: str
    credential_id: str | None
    template_id: str | None
    is_acknowledged: bool
    acknowledged_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AlertAcknowledgeRequest(BaseModel):
    """Request payload for acknowledging a governance alert."""

    actor: str = Field(default="system")
