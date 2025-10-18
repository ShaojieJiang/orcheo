"""Credential template registry and governance helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable
from uuid import UUID

from orcheo.models import (
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialKind,
    CredentialMetadata,
    CredentialScope,
    OAuthTokenSecrets,
)
from orcheo.vault import BaseCredentialVault


@dataclass(slots=True)
class CredentialTemplate:
    """Describes reusable configuration for provider credentials."""

    slug: str
    provider: str
    description: str
    default_scopes: tuple[str, ...] = field(default_factory=tuple)
    kind: CredentialKind = CredentialKind.SECRET
    requires_refresh_token: bool = False
    rotation_interval_days: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def build_oauth_tokens(
        self,
        *,
        access_token: str,
        refresh_token: str | None,
        expires_in_seconds: int | None = None,
    ) -> OAuthTokenSecrets:
        """Convenience helper to construct OAuth tokens for the template."""

        expires_at = (
            datetime.now(tz=UTC) + timedelta(seconds=expires_in_seconds)
            if expires_in_seconds
            else None
        )
        if self.requires_refresh_token and not refresh_token:
            msg = f"Template {self.slug} requires a refresh token"
            raise ValueError(msg)
        return OAuthTokenSecrets(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )


@dataclass(slots=True)
class GovernanceAlert:
    """Represents a governance finding raised for a credential."""

    credential_id: UUID
    template_slug: str
    message: str
    severity: str = "warning"


@dataclass(slots=True)
class CredentialTemplateRegistry:
    """Registry tracking credential templates and issued credentials."""

    _templates: dict[str, CredentialTemplate] = field(default_factory=dict)
    _assignments: dict[UUID, set[UUID]] = field(default_factory=dict)
    _issued_templates: dict[UUID, str] = field(default_factory=dict)

    def register(self, template: CredentialTemplate) -> None:
        """Register or replace a credential template."""

        if not template.slug:
            msg = "Template slug cannot be empty"
            raise ValueError(msg)
        self._templates[template.slug] = template

    def get(self, slug: str) -> CredentialTemplate:
        """Return the template for the provided slug."""

        try:
            return self._templates[slug]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise KeyError(f"Unknown credential template '{slug}'") from exc

    def list_templates(self) -> list[CredentialTemplate]:
        """Return registered templates in registration order."""

        return list(self._templates.values())

    def instantiate(
        self,
        slug: str,
        *,
        vault: BaseCredentialVault,
        workflow_id: UUID,
        name: str,
        secret: str,
        actor: str,
        scopes: Iterable[str] | None = None,
        oauth_tokens: OAuthTokenSecrets | None = None,
    ) -> CredentialMetadata:
        """Create a credential instance bound to the workflow."""

        template = self.get(slug)
        scope = CredentialScope.for_workflows(workflow_id)
        effective_scopes = list(scopes) if scopes is not None else list(template.default_scopes)
        metadata = vault.create_credential(
            name=name,
            provider=template.provider,
            scopes=effective_scopes,
            secret=secret,
            actor=actor,
            scope=scope,
            kind=template.kind,
            oauth_tokens=oauth_tokens,
        )
        assignments = self._assignments.setdefault(workflow_id, set())
        assignments.add(metadata.id)
        self._issued_templates[metadata.id] = template.slug
        return metadata

    def generate_alerts(
        self,
        *,
        vault: BaseCredentialVault,
        workflow_id: UUID,
        now: datetime | None = None,
    ) -> list[GovernanceAlert]:
        """Evaluate credentials issued from templates and produce alerts."""

        reference_time = now or datetime.now(tz=UTC)
        context = CredentialAccessContext(workflow_id=workflow_id)
        alerts: list[GovernanceAlert] = []
        assigned_ids = self._assignments.get(workflow_id, set())
        for metadata in vault.list_credentials(context=context):
            if metadata.id not in assigned_ids:
                continue
            template = self._template_for(metadata)
            if template is None:
                continue
            if template.requires_refresh_token and metadata.kind is CredentialKind.OAUTH:
                tokens = metadata.reveal_oauth_tokens(cipher=vault.cipher)
                if tokens is None or not tokens.refresh_token:
                    alerts.append(
                        GovernanceAlert(
                            credential_id=metadata.id,
                            template_slug=template.slug,
                            message="Refresh token missing for OAuth credential",
                            severity="critical",
                        )
                    )
            if (
                template.rotation_interval_days
                and metadata.last_rotated_at
                and metadata.last_rotated_at
                <= reference_time - timedelta(days=template.rotation_interval_days)
            ):
                alerts.append(
                    GovernanceAlert(
                        credential_id=metadata.id,
                        template_slug=template.slug,
                        message="Credential rotation overdue",
                        severity="high",
                    )
                )
            if metadata.health.status is CredentialHealthStatus.UNHEALTHY:
                reason = metadata.health.failure_reason or "unknown reason"
                alerts.append(
                    GovernanceAlert(
                        credential_id=metadata.id,
                        template_slug=template.slug,
                        message=f"Credential health reported unhealthy: {reason}",
                        severity="high",
                    )
                )
        return alerts

    def _template_for(self, metadata: CredentialMetadata) -> CredentialTemplate | None:
        slug = self._issued_templates.get(metadata.id)
        if slug is None:
            return None
        return self._templates.get(slug)


def default_registry() -> CredentialTemplateRegistry:
    """Return a registry pre-populated with common provider templates."""

    registry = CredentialTemplateRegistry()
    registry.register(
        CredentialTemplate(
            slug="slack-bot",
            provider="slack",
            description="Slack bot token with chat:write scope",
            default_scopes=("chat:write",),
            kind=CredentialKind.OAUTH,
            requires_refresh_token=True,
            rotation_interval_days=30,
            metadata={"icon": "slack"},
        )
    )
    registry.register(
        CredentialTemplate(
            slug="http-webhook",
            provider="http",  # secret used for webhook signing
            description="HMAC secret used for webhook validation",
            default_scopes=("webhook:sign",),
            kind=CredentialKind.SECRET,
            rotation_interval_days=90,
        )
    )
    return registry


__all__ = [
    "CredentialTemplate",
    "CredentialTemplateRegistry",
    "GovernanceAlert",
    "default_registry",
]
