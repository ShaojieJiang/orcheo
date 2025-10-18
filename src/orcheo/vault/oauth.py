"""OAuth credential refresh and health validation service."""

from __future__ import annotations
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID
from orcheo.models import (
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialIssuancePolicy,
    CredentialKind,
    CredentialMetadata,
    CredentialTemplate,
    GovernanceAlertKind,
    OAuthTokenSecrets,
    SecretGovernanceAlertSeverity,
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

    def issue_from_template(
        self,
        *,
        template_id: UUID,
        secret: str,
        actor: str,
        name: str | None = None,
        scopes: Sequence[str] | None = None,
        context: CredentialAccessContext | None = None,
        oauth_tokens: OAuthTokenSecrets | None = None,
    ) -> CredentialMetadata:
        """Instantiate a credential using the provided template defaults."""
        access_context = context or CredentialAccessContext()
        template = self._vault.get_template(
            template_id=template_id, context=access_context
        )
        self._validate_template_policy(
            template.issuance_policy, oauth_tokens=oauth_tokens
        )
        metadata = self._vault.create_credential(
            name=name or template.name,
            provider=template.provider,
            scopes=scopes or template.scopes,
            secret=secret,
            actor=actor,
            scope=template.scope,
            kind=template.kind,
            oauth_tokens=oauth_tokens,
            template_id=template.id,
        )
        self._vault.record_template_issuance(
            template_id=template.id,
            actor=actor,
            credential_id=metadata.id,
            context=access_context,
        )
        return metadata

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
            result = await self._process_oauth_credential(
                metadata, context=context, actor_name=actor_name
            )
            results.append(result)

        report = CredentialHealthReport(
            workflow_id=workflow_id,
            results=results,
            checked_at=datetime.now(tz=UTC),
        )
        self._reports[workflow_id] = report
        return report

    async def _process_oauth_credential(
        self,
        metadata: CredentialMetadata,
        *,
        context: CredentialAccessContext,
        actor_name: str,
    ) -> CredentialHealthResult:
        provider = self._providers.get(metadata.provider)
        if provider is None:
            updated = self._vault.mark_health(
                credential_id=metadata.id,
                status=CredentialHealthStatus.UNHEALTHY,
                reason=f"No OAuth provider registered for '{metadata.provider}'",
                actor=actor_name,
                context=context,
            )
            self._record_validation_failure(
                metadata=metadata,
                actor_name=actor_name,
                context=context,
                message=f"No provider registered for {metadata.provider}.",
            )
            return CredentialHealthResult(
                credential_id=updated.id,
                name=updated.name,
                provider=updated.provider,
                status=updated.health.status,
                last_checked_at=updated.health.last_checked_at,
                failure_reason=updated.health.failure_reason,
            )

        metadata_copy = metadata
        tokens = metadata_copy.reveal_oauth_tokens(cipher=self._vault.cipher)
        alerts_triggered: set[GovernanceAlertKind] = set()
        template = self._load_template_for_metadata(metadata, context)
        self._apply_rotation_policy(
            template,
            metadata,
            alerts_triggered,
            context=context,
            actor_name=actor_name,
        )

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
            alerts_triggered.add(GovernanceAlertKind.VALIDATION_FAILED)
            self._record_validation_failure(
                metadata=metadata,
                actor_name=actor_name,
                context=context,
                message=str(exc),
            )
            return CredentialHealthResult(
                credential_id=updated.id,
                name=updated.name,
                provider=updated.provider,
                status=updated.health.status,
                last_checked_at=updated.health.last_checked_at,
                failure_reason=updated.health.failure_reason,
            )

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

        self._apply_token_expiry_alert(
            metadata,
            tokens,
            alerts_triggered,
            context=context,
            actor_name=actor_name,
        )

        result = CredentialHealthResult(
            credential_id=updated.id,
            name=updated.name,
            provider=updated.provider,
            status=updated.health.status,
            last_checked_at=updated.health.last_checked_at,
            failure_reason=updated.health.failure_reason,
        )

        if validation.status is CredentialHealthStatus.UNHEALTHY:
            alerts_triggered.add(GovernanceAlertKind.VALIDATION_FAILED)
            self._record_validation_failure(
                metadata=metadata,
                actor_name=actor_name,
                context=context,
                message=validation.failure_reason or "Credential validation failed",
            )
        elif not alerts_triggered:
            self._vault.resolve_alerts_for_credential(updated.id, actor=actor_name)

        return result

    def _load_template_for_metadata(
        self,
        metadata: CredentialMetadata,
        context: CredentialAccessContext,
    ) -> CredentialTemplate | None:
        if metadata.template_id is None:
            return None
        try:
            return self._vault.get_template(
                template_id=metadata.template_id,
                context=context,
            )
        except Exception:  # pragma: no cover - missing template should not block
            return None

    def _apply_rotation_policy(
        self,
        template: CredentialTemplate | None,
        metadata: CredentialMetadata,
        alerts_triggered: set[GovernanceAlertKind],
        *,
        context: CredentialAccessContext,
        actor_name: str,
    ) -> None:
        if template and template.issuance_policy.requires_rotation(
            last_rotated_at=metadata.last_rotated_at
        ):
            alerts_triggered.add(GovernanceAlertKind.ROTATION_OVERDUE)
            self._vault.record_alert(
                kind=GovernanceAlertKind.ROTATION_OVERDUE,
                severity=SecretGovernanceAlertSeverity.WARNING,
                message="Credential rotation is overdue per template policy.",
                actor=actor_name,
                credential_id=metadata.id,
                template_id=metadata.template_id,
                context=context,
            )

    def _apply_token_expiry_alert(
        self,
        metadata: CredentialMetadata,
        tokens: OAuthTokenSecrets | None,
        alerts_triggered: set[GovernanceAlertKind],
        *,
        context: CredentialAccessContext,
        actor_name: str,
    ) -> None:
        if tokens is None or tokens.expires_at is None:
            return
        now = datetime.now(tz=UTC)
        if tokens.expires_at <= now + self._refresh_margin:
            alerts_triggered.add(GovernanceAlertKind.TOKEN_EXPIRING)
            self._vault.record_alert(
                kind=GovernanceAlertKind.TOKEN_EXPIRING,
                severity=SecretGovernanceAlertSeverity.WARNING,
                message=f"Token expires at {tokens.expires_at.isoformat()}",
                actor=actor_name,
                credential_id=metadata.id,
                context=context,
            )

    def _record_validation_failure(
        self,
        *,
        metadata: CredentialMetadata,
        actor_name: str,
        context: CredentialAccessContext,
        message: str,
    ) -> None:
        self._vault.record_alert(
            kind=GovernanceAlertKind.VALIDATION_FAILED,
            severity=SecretGovernanceAlertSeverity.CRITICAL,
            message=message,
            actor=actor_name,
            credential_id=metadata.id,
            context=context,
        )

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

    def _validate_template_policy(
        self,
        policy: CredentialIssuancePolicy,
        *,
        oauth_tokens: OAuthTokenSecrets | None,
    ) -> None:
        if not policy.require_refresh_token:
            return
        if oauth_tokens is None or oauth_tokens.refresh_token is None:
            msg = "Template requires a refresh token for issued credentials."
            raise ValueError(msg)


__all__ = [
    "CredentialHealthError",
    "CredentialHealthGuard",
    "CredentialHealthReport",
    "CredentialHealthResult",
    "OAuthCredentialService",
    "OAuthProvider",
    "OAuthValidationResult",
]
