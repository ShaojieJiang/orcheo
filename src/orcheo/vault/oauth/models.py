"""OAuth credential data contracts and protocols."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID
from orcheo.models import (
    CredentialHealthStatus,
    CredentialMetadata,
    OAuthTokenSecrets,
)


@dataclass(slots=True)
class OAuthValidationResult:
    """Result returned by providers after validating OAuth credentials."""

    status: CredentialHealthStatus
    failure_reason: str | None = None


class OAuthProvider(Protocol):
    """Protocol describing provider specific OAuth refresh/validation hooks."""

    async def refresh_tokens(
        self,
        metadata: CredentialMetadata,
        tokens: OAuthTokenSecrets | None,
    ) -> OAuthTokenSecrets | None:
        """Return updated OAuth tokens or ``None`` if refresh is unnecessary."""

    async def validate_tokens(
        self,
        metadata: CredentialMetadata,
        tokens: OAuthTokenSecrets | None,
    ) -> OAuthValidationResult:
        """Return the health status for the provided OAuth tokens."""


@dataclass(slots=True)
class CredentialHealthResult:
    """Represents the health outcome for a single credential."""

    credential_id: UUID
    name: str
    provider: str
    status: CredentialHealthStatus
    last_checked_at: datetime | None
    failure_reason: str | None


@dataclass(slots=True)
class CredentialHealthReport:
    """Aggregated health results for all credentials bound to a workflow."""

    workflow_id: UUID
    results: list[CredentialHealthResult]
    checked_at: datetime

    @property
    def is_healthy(self) -> bool:
        """Return True when all credentials in the report are healthy."""
        return all(
            result.status is CredentialHealthStatus.HEALTHY for result in self.results
        )

    @property
    def failures(self) -> list[str]:
        """Return failure reasons for credentials that are not healthy."""
        return [
            result.failure_reason
            or f"Credential {result.credential_id} reported unhealthy"
            for result in self.results
            if result.status is CredentialHealthStatus.UNHEALTHY
        ]


class CredentialHealthGuard(Protocol):
    """Protocol used by trigger layers to query credential health state."""

    def is_workflow_healthy(self, workflow_id: UUID) -> bool:
        """Return whether the cached health report for the workflow is healthy."""

    def get_report(self, workflow_id: UUID) -> CredentialHealthReport | None:
        """Return the last health report evaluated for the workflow if present."""


class CredentialHealthError(RuntimeError):
    """Raised when workflow execution is blocked by unhealthy credentials."""

    def __init__(self, report: CredentialHealthReport) -> None:
        """Initialize the error with the report that triggered the failure."""
        failures = "; ".join(report.failures) or "unknown reason"
        message = f"Workflow {report.workflow_id} has unhealthy credentials: {failures}"
        super().__init__(message)
        self.report = report


__all__ = [
    "CredentialHealthError",
    "CredentialHealthGuard",
    "CredentialHealthReport",
    "CredentialHealthResult",
    "OAuthProvider",
    "OAuthValidationResult",
]
