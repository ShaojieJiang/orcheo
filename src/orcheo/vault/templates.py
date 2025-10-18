"""Credential template registry and helpers for secure issuance."""

from __future__ import annotations
from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID
from pydantic import BaseModel, Field
from orcheo.models import (
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialKind,
    CredentialScope,
    OAuthTokenSecrets,
)


if TYPE_CHECKING:
    from orcheo.vault import BaseCredentialVault


class CredentialTemplateField(BaseModel):
    """Describes an input field that must be collected for a template."""

    key: str
    label: str
    secret: bool = False
    required: bool = True
    description: str | None = None


class SecretGovernanceAlert(BaseModel):
    """Represents a governance alert produced during issuance or rotation."""

    severity: str = Field(description="alert severity", default="warning")
    message: str


class CredentialTemplate(BaseModel):
    """Declarative descriptor for issuing credentials consistently."""

    name: str
    provider: str
    kind: CredentialKind = Field(default=CredentialKind.SECRET)
    scopes: list[str] = Field(default_factory=list)
    fields: list[CredentialTemplateField] = Field(default_factory=list)
    default_scope: CredentialScope = Field(
        default_factory=CredentialScope.unrestricted,
    )
    default_token_ttl_hours: int | None = Field(default=None)
    governance_window_hours: int = Field(
        default=24,
        description="Hours before expiry that should raise governance alerts.",
    )

    def validate_inputs(self, values: Mapping[str, str]) -> None:
        """Ensure required template fields are present before issuance."""
        missing = [
            field.label
            for field in self.fields
            if field.required and not values.get(field.key)
        ]
        if missing:
            formatted = ", ".join(missing)
            msg = f"Missing required fields: {formatted}"
            raise ValueError(msg)

    def _compute_scope(
        self, workflow_id: UUID | None, scope: CredentialScope | None
    ) -> CredentialScope:
        if scope is not None:
            return scope
        return self.default_scope.model_copy(deep=True)

    def _resolve_tokens(
        self,
        values: Mapping[str, str],
    ) -> OAuthTokenSecrets | None:
        if self.kind is not CredentialKind.OAUTH:
            return None
        access = values.get("access_token")
        refresh = values.get("refresh_token")
        expires_at: datetime | None = None
        if ttl := self.default_token_ttl_hours:
            expires_at = datetime.now(tz=UTC) + timedelta(hours=ttl)
        if access is None and refresh is None and expires_at is None:
            return None
        return OAuthTokenSecrets(
            access_token=access,
            refresh_token=refresh,
            expires_at=expires_at,
        )

    def issue(
        self,
        vault: BaseCredentialVault,
        *,
        actor: str,
        secret: str,
        workflow_id: UUID | None = None,
        scope: CredentialScope | None = None,
        name: str | None = None,
        overrides: Mapping[str, str] | None = None,
    ) -> tuple[UUID, list[SecretGovernanceAlert]]:
        """Issue a credential for the template using the provided vault."""
        values = dict(overrides or {})
        for field in self.fields:
            if field.secret and field.key not in values:
                values[field.key] = secret
        self.validate_inputs(values)
        computed_scope = self._compute_scope(workflow_id, scope)
        metadata = vault.create_credential(
            name=name or self.name,
            provider=self.provider,
            scopes=self.scopes or list(values.get("scopes", [])),
            secret=secret,
            actor=actor,
            scope=computed_scope,
            kind=self.kind,
            oauth_tokens=self._resolve_tokens(values),
        )
        alerts: list[SecretGovernanceAlert] = []
        if metadata.health.status is CredentialHealthStatus.UNKNOWN:
            message = (
                "Credential health is unknown; validation must occur before execution."
            )
            alerts.append(
                SecretGovernanceAlert(
                    message=message,
                )
            )
        window = timedelta(hours=self.governance_window_hours)
        if (
            metadata.oauth_tokens
            and metadata.oauth_tokens.expires_at
            and metadata.oauth_tokens.expires_at <= datetime.now(tz=UTC) + window
        ):
            alerts.append(
                SecretGovernanceAlert(
                    severity="critical",
                    message=(
                        "OAuth token expires within governance window; "
                        "refresh required."
                    ),
                )
            )
        return metadata.id, alerts


@dataclass(slots=True)
class CredentialTemplateRegistry:
    """Container managing credential templates with helper accessors."""

    templates: MutableMapping[str, CredentialTemplate]

    def register(self, template: CredentialTemplate) -> None:
        """Register a credential template, replacing any existing entry."""
        key = template.provider.lower()
        self.templates[key] = template

    def get(self, provider: str) -> CredentialTemplate | None:
        """Return the template for the provider when available."""
        return self.templates.get(provider.lower())

    def list_templates(self) -> list[CredentialTemplate]:
        """Return registered templates sorted by provider name."""
        return sorted(self.templates.values(), key=lambda template: template.provider)

    def issue_from_provider(
        self,
        provider: str,
        vault: BaseCredentialVault,
        *,
        actor: str,
        secret: str,
        workflow_id: UUID | None = None,
        scope: CredentialScope | None = None,
        overrides: Mapping[str, str] | None = None,
    ) -> tuple[UUID, list[SecretGovernanceAlert]]:
        """Issue a credential from the provider template."""
        template = self.get(provider)
        if template is None:
            msg = f"No credential template registered for provider '{provider}'"
            raise KeyError(msg)
        name = overrides.get("name") if overrides else None
        return template.issue(
            vault,
            actor=actor,
            secret=secret,
            workflow_id=workflow_id,
            scope=scope,
            overrides=overrides,
            name=name,
        )


def builtin_templates() -> CredentialTemplateRegistry:
    """Return a registry pre-populated with common Orcheo templates."""
    registry = CredentialTemplateRegistry(templates={})
    registry.register(
        CredentialTemplate(
            name="Slack Bot",  # Slack incoming webhooks or bot tokens
            provider="slack",
            scopes=["chat:write", "channels:history"],
            fields=[
                CredentialTemplateField(
                    key="secret",
                    label="Bot token",
                    secret=True,
                    description="xoxb- token issued by Slack",
                ),
            ],
            governance_window_hours=12,
        )
    )
    registry.register(
        CredentialTemplate(
            name="Telegram Bot",
            provider="telegram",
            scopes=["messages:write"],
            fields=[
                CredentialTemplateField(
                    key="secret",
                    label="Bot API token",
                    secret=True,
                    description="Token provided by BotFather",
                )
            ],
            governance_window_hours=12,
        )
    )
    registry.register(
        CredentialTemplate(
            name="Discord Bot",
            provider="discord",
            scopes=["messages:write"],
            fields=[
                CredentialTemplateField(
                    key="secret",
                    label="Bot token",
                    secret=True,
                    description="Discord bot authorization token",
                )
            ],
            governance_window_hours=12,
        )
    )
    registry.register(
        CredentialTemplate(
            name="OpenAI OAuth",  # Example OAuth template
            provider="openai",
            kind=CredentialKind.OAUTH,
            scopes=["responses.read", "responses.write"],
            fields=[
                CredentialTemplateField(
                    key="access_token",
                    label="Access token",
                    secret=True,
                    required=False,
                ),
                CredentialTemplateField(
                    key="refresh_token",
                    label="Refresh token",
                    secret=True,
                ),
            ],
            default_token_ttl_hours=12,
            governance_window_hours=6,
        )
    )
    return registry


def governance_audit(
    vault: BaseCredentialVault,
    *,
    registry: CredentialTemplateRegistry,
    workflow_id: UUID,
) -> Iterable[SecretGovernanceAlert]:
    """Evaluate stored credentials against template governance policies."""
    context = CredentialAccessContext(workflow_id=workflow_id)
    for metadata in vault.list_credentials(context=context):
        template = registry.get(metadata.provider)
        if template is None:
            continue
        window = timedelta(hours=template.governance_window_hours)
        if (
            metadata.kind is CredentialKind.OAUTH
            and metadata.oauth_tokens
            and metadata.oauth_tokens.expires_at
            and metadata.oauth_tokens.expires_at <= datetime.now(tz=UTC) + window
        ):
            yield SecretGovernanceAlert(
                severity="critical",
                message=(
                    f"Credential {metadata.name} ({metadata.provider}) expires within "
                    f"{template.governance_window_hours} hours"
                ),
            )


__all__ = [
    "CredentialTemplate",
    "CredentialTemplateField",
    "CredentialTemplateRegistry",
    "SecretGovernanceAlert",
    "builtin_templates",
    "governance_audit",
]
