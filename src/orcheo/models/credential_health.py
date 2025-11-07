"""Credential health tracking primitives."""

from __future__ import annotations
from collections.abc import MutableMapping
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from pydantic import Field
from orcheo.models.base import OrcheoBaseModel, _utcnow


__all__ = [
    "CredentialHealth",
    "CredentialHealthStatus",
    "CredentialIssuancePolicy",
]


class CredentialHealthStatus(str, Enum):
    """Represents the evaluated health state for a credential."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class CredentialHealth(OrcheoBaseModel):
    """Tracks the last known health evaluation for a credential."""

    status: CredentialHealthStatus = Field(default=CredentialHealthStatus.UNKNOWN)
    last_checked_at: datetime | None = None
    failure_reason: str | None = None

    def update(
        self, *, status: CredentialHealthStatus, reason: str | None = None
    ) -> None:
        """Update the health status and timestamp for the credential."""
        self.status = status
        self.last_checked_at = _utcnow()
        self.failure_reason = reason

    def redact(self) -> MutableMapping[str, Any]:
        """Return a redacted health payload for logging."""
        return {
            "status": self.status.value,
            "last_checked_at": self.last_checked_at.isoformat()
            if self.last_checked_at
            else None,
            "failure_reason": self.failure_reason,
        }


class CredentialIssuancePolicy(OrcheoBaseModel):
    """Declares default rotation and expiry requirements for credentials."""

    require_refresh_token: bool = False
    rotation_period_days: int | None = Field(default=None, ge=1)
    expiry_threshold_minutes: int = Field(default=60, ge=1)

    def requires_rotation(
        self, *, last_rotated_at: datetime | None, now: datetime | None = None
    ) -> bool:
        """Return ``True`` when the credential should be rotated."""
        if self.rotation_period_days is None or last_rotated_at is None:
            return False
        current = now or _utcnow()
        deadline = last_rotated_at + timedelta(days=self.rotation_period_days)
        return current >= deadline
