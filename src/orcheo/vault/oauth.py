"""OAuth credential refresh and health validation service."""

from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID
from orcheo.models import (
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialKind,
    CredentialMetadata,
    OAuthTokenSecrets,
)
from orcheo.vault import BaseCredentialVault


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


class OAuthCredentialService(CredentialHealthGuard):
    """Coordinates OAuth token refresh and health validation operations."""

    def __init__(
        self,
        vault: BaseCredentialVault,
        *,
        token_ttl_seconds: int,
        providers: Mapping[str, OAuthProvider] | None = None,
        default_actor: str = "system",
    ) -> None:
        """Create the OAuth credential service with provider refresh hooks."""
        if token_ttl_seconds <= 0:
            msg = "token_ttl_seconds must be greater than zero"
            raise ValueError(msg)
        self._vault = vault
        self._providers: dict[str, OAuthProvider] = dict(providers or {})
        self._default_actor = default_actor
        self._refresh_margin = timedelta(seconds=token_ttl_seconds)
        self._reports: dict[UUID, CredentialHealthReport] = {}

    def register_provider(self, provider: str, handler: OAuthProvider) -> None:
        """Register or replace the OAuth provider handler."""
        if not provider:
            msg = "provider cannot be empty"
            raise ValueError(msg)
        self._providers[provider] = handler

    def is_workflow_healthy(self, workflow_id: UUID) -> bool:
        """Return True when the cached health report has no failures."""
        report = self._reports.get(workflow_id)
        return True if report is None else report.is_healthy

    def get_report(self, workflow_id: UUID) -> CredentialHealthReport | None:
        """Return the most recent credential health report for the workflow."""
        return self._reports.get(workflow_id)

    async def ensure_workflow_health(
        self, workflow_id: UUID, *, actor: str | None = None
    ) -> CredentialHealthReport:
        """Evaluate and refresh credentials prior to workflow execution."""
        context = CredentialAccessContext(workflow_id=workflow_id)
        credentials = self._vault.list_credentials(context=context)
        actor_name = actor or self._default_actor
        results: list[CredentialHealthResult] = []

        for metadata in credentials:
            if metadata.kind is not CredentialKind.OAUTH:
                updated = self._vault.mark_health(
                    credential_id=metadata.id,
                    status=CredentialHealthStatus.HEALTHY,
                    reason=None,
                    actor=actor_name,
                    context=context,
                )
                results.append(
                    CredentialHealthResult(
                        credential_id=updated.id,
                        name=updated.name,
                        provider=updated.provider,
                        status=updated.health.status,
                        last_checked_at=updated.health.last_checked_at,
                        failure_reason=updated.health.failure_reason,
                    )
                )
                continue

            provider = self._providers.get(metadata.provider)
            if provider is None:
                updated = self._vault.mark_health(
                    credential_id=metadata.id,
                    status=CredentialHealthStatus.UNHEALTHY,
                    reason=f"No OAuth provider registered for '{metadata.provider}'",
                    actor=actor_name,
                    context=context,
                )
                results.append(
                    CredentialHealthResult(
                        credential_id=updated.id,
                        name=updated.name,
                        provider=updated.provider,
                        status=updated.health.status,
                        last_checked_at=updated.health.last_checked_at,
                        failure_reason=updated.health.failure_reason,
                    )
                )
                continue

            metadata_copy = metadata
            tokens = metadata_copy.reveal_oauth_tokens(cipher=self._vault.cipher)

            try:
                if self._should_refresh(tokens):
                    refreshed = await provider.refresh_tokens(metadata_copy, tokens)
                    if refreshed is not None:
                        metadata_copy = self._vault.update_oauth_tokens(
                            credential_id=metadata.id,
                            tokens=refreshed,
                            actor=actor_name,
                            context=context,
                        )
                        tokens = metadata_copy.reveal_oauth_tokens(
                            cipher=self._vault.cipher
                        )
            except Exception as exc:  # pragma: no cover - provider errors handled
                updated = self._vault.mark_health(
                    credential_id=metadata.id,
                    status=CredentialHealthStatus.UNHEALTHY,
                    reason=str(exc),
                    actor=actor_name,
                    context=context,
                )
                results.append(
                    CredentialHealthResult(
                        credential_id=updated.id,
                        name=updated.name,
                        provider=updated.provider,
                        status=updated.health.status,
                        last_checked_at=updated.health.last_checked_at,
                        failure_reason=updated.health.failure_reason,
                    )
                )
                continue

            try:
                validation = await provider.validate_tokens(metadata_copy, tokens)
            except Exception as exc:  # pragma: no cover - provider errors handled
                validation = OAuthValidationResult(
                    status=CredentialHealthStatus.UNHEALTHY,
                    failure_reason=str(exc),
                )

            updated = self._vault.mark_health(
                credential_id=metadata.id,
                status=validation.status,
                reason=validation.failure_reason,
                actor=actor_name,
                context=context,
            )
            results.append(
                CredentialHealthResult(
                    credential_id=updated.id,
                    name=updated.name,
                    provider=updated.provider,
                    status=updated.health.status,
                    last_checked_at=updated.health.last_checked_at,
                    failure_reason=updated.health.failure_reason,
                )
            )

        report = CredentialHealthReport(
            workflow_id=workflow_id,
            results=results,
            checked_at=datetime.now(tz=UTC),
        )
        self._reports[workflow_id] = report
        return report

    def require_healthy(self, workflow_id: UUID) -> None:
        """Raise an error if the cached report deems the workflow unhealthy."""
        report = self._reports.get(workflow_id)
        if report is None or report.is_healthy:
            return
        raise CredentialHealthError(report)

    def _should_refresh(self, tokens: OAuthTokenSecrets | None) -> bool:
        if tokens is None:
            return True
        if tokens.expires_at is None:
            return False
        now = datetime.now(tz=UTC)
        return tokens.expires_at <= now + self._refresh_margin


__all__ = [
    "CredentialHealthError",
    "CredentialHealthGuard",
    "CredentialHealthReport",
    "CredentialHealthResult",
    "OAuthCredentialService",
    "OAuthProvider",
    "OAuthValidationResult",
]
