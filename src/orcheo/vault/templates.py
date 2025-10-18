"""Credential template registry with governance alerting support."""

from __future__ import annotations
import builtins
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID
from orcheo.models import (
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialKind,
    CredentialMetadata,
    CredentialScope,
    OAuthTokenSecrets,
)


if TYPE_CHECKING:  # pragma: no cover - imported for typing only
    from orcheo.vault import BaseCredentialVault


FieldValidator = Callable[[str], None]


class GovernanceAlertLevel(str, Enum):
    """Represents the severity for a governance alert."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class GovernanceAlertKind(str, Enum):
    """Types of alerts emitted by credential governance checks."""

    EXPIRING = "expiring"
    MISSING_SECRET = "missing_secret"
    ROTATION_OVERDUE = "rotation_overdue"
    UNUSED_SCOPE = "unused_scope"
    HEALTH_UNHEALTHY = "health_unhealthy"


@dataclass(slots=True)
class SecretGovernanceAlert:
    """Alert surfaced during credential governance evaluation."""

    credential_id: UUID
    kind: GovernanceAlertKind
    level: GovernanceAlertLevel
    message: str


@dataclass(slots=True)
class TemplateField:
    """Describes a single value required to materialise a template."""

    key: str
    label: str
    description: str
    required: bool = True
    secret: bool = False
    validator: FieldValidator | None = None
    default: str | None = None

    def validate(self, value: str | None) -> str:
        """Return the validated value or raise ``ValueError``."""
        if value is None:
            if self.required and self.default is None:
                msg = f"Field '{self.key}' is required"
                raise ValueError(msg)
            if self.default is not None:
                value = self.default
            else:
                return ""
        if self.validator is not None:
            self.validator(value)
        return value


@dataclass(slots=True)
class CredentialTemplate:
    """Template describing how to create a governed credential."""

    slug: str
    name: str
    provider: str
    description: str
    scopes: tuple[str, ...]
    fields: tuple[TemplateField, ...]
    default_scope: CredentialScope = field(default_factory=CredentialScope.unrestricted)
    rotation_days: int = 90

    def validate_payload(self, payload: Mapping[str, str]) -> dict[str, str]:
        """Validate template payload returning a sanitized dictionary."""
        sanitized: dict[str, str] = {}
        data = dict(payload)
        for field_def in self.fields:
            value = data.get(field_def.key)
            sanitized[field_def.key] = field_def.validate(value)
        return sanitized

    def issue(
        self,
        *,
        vault: BaseCredentialVault,
        actor: str,
        workflow_id: UUID | None,
        payload: Mapping[str, str],
        scopes: CredentialScope | None = None,
        oauth_tokens: OAuthTokenSecrets | None = None,
    ) -> CredentialMetadata:
        """Create the credential in the provided vault."""
        values = self.validate_payload(payload)
        secret = values.get("secret") or ""
        if not secret:
            raise ValueError("Template payload must include a 'secret' value")

        scope = scopes or self.default_scope
        if workflow_id:
            scope = CredentialScope.for_workflows(workflow_id)

        metadata = vault.create_credential(
            name=self.name,
            provider=self.provider,
            scopes=list(self.scopes),
            secret=secret,
            actor=actor,
            scope=scope,
            kind=CredentialKind.OAUTH
            if oauth_tokens is not None
            else CredentialKind.SECRET,
            oauth_tokens=oauth_tokens,
        )
        return metadata

    def evaluate_governance(
        self,
        *,
        metadata: CredentialMetadata,
        now: datetime | None = None,
    ) -> list[SecretGovernanceAlert]:
        """Return governance alerts derived from metadata state."""
        current = now or datetime.now(tz=UTC)
        alerts: list[SecretGovernanceAlert] = []

        if metadata.health.status is CredentialHealthStatus.UNHEALTHY:
            alerts.append(
                SecretGovernanceAlert(
                    credential_id=metadata.id,
                    kind=GovernanceAlertKind.HEALTH_UNHEALTHY,
                    level=GovernanceAlertLevel.CRITICAL,
                    message=metadata.health.failure_reason
                    or "Credential reported unhealthy",
                )
            )

        if metadata.oauth_tokens and metadata.oauth_tokens.expires_at:
            expiry = metadata.oauth_tokens.expires_at
            if expiry <= current + timedelta(days=7):
                alerts.append(
                    SecretGovernanceAlert(
                        credential_id=metadata.id,
                        kind=GovernanceAlertKind.EXPIRING,
                        level=GovernanceAlertLevel.WARNING,
                        message=("OAuth access token is nearing expiry"),
                    )
                )

        if metadata.last_rotated_at:
            rotate_by = metadata.last_rotated_at + timedelta(days=self.rotation_days)
            if rotate_by <= current:
                alerts.append(
                    SecretGovernanceAlert(
                        credential_id=metadata.id,
                        kind=GovernanceAlertKind.ROTATION_OVERDUE,
                        level=GovernanceAlertLevel.WARNING,
                        message=("Credential rotation window has elapsed"),
                    )
                )

        if not metadata.scopes:
            alerts.append(
                SecretGovernanceAlert(
                    credential_id=metadata.id,
                    kind=GovernanceAlertKind.UNUSED_SCOPE,
                    level=GovernanceAlertLevel.INFO,
                    message="Template scopes are empty; verify runtime usage",
                )
            )

        return alerts


class TemplateRegistry:
    """In-memory registry for credential templates."""

    def __init__(self) -> None:
        """Initialise an empty template registry."""
        self._templates: dict[str, CredentialTemplate] = {}

    def register(self, template: CredentialTemplate) -> None:
        """Register a new template, replacing any existing one."""
        if not template.slug:
            msg = "Template slug cannot be empty"
            raise ValueError(msg)
        self._templates[template.slug] = template

    def get(self, slug: str) -> CredentialTemplate:
        """Return the template identified by the slug."""
        try:
            return self._templates[slug]
        except KeyError as exc:  # pragma: no cover - defensive
            msg = f"Unknown credential template: {slug}"
            raise KeyError(msg) from exc

    def list(self) -> list[CredentialTemplate]:
        """Return registered templates sorted by name."""
        return sorted(self._templates.values(), key=lambda tpl: tpl.name.lower())

    def issue_from_template(
        self,
        slug: str,
        *,
        vault: BaseCredentialVault,
        actor: str,
        workflow_id: UUID | None,
        payload: Mapping[str, str],
        oauth_tokens: OAuthTokenSecrets | None = None,
    ) -> CredentialMetadata:
        """Issue a credential using the specified template."""
        template = self.get(slug)
        metadata = template.issue(
            vault=vault,
            actor=actor,
            workflow_id=workflow_id,
            payload=payload,
            oauth_tokens=oauth_tokens,
        )
        return metadata

    def evaluate_workflow_governance(
        self,
        *,
        vault: BaseCredentialVault,
        workflow_id: UUID,
        context: CredentialAccessContext | None = None,
        now: datetime | None = None,
    ) -> builtins.list[SecretGovernanceAlert]:
        """Run governance checks for all workflow credentials."""
        alerts: builtins.list[SecretGovernanceAlert] = []
        access_context = context or CredentialAccessContext(workflow_id=workflow_id)
        for metadata in vault.list_credentials(context=access_context):
            template = self._templates.get(metadata.provider)
            if template is None:
                continue
            alerts.extend(template.evaluate_governance(metadata=metadata, now=now))
        return alerts


def build_default_registry() -> TemplateRegistry:
    """Return a registry pre-populated with common templates."""
    registry = TemplateRegistry()

    registry.register(
        CredentialTemplate(
            slug="slack",  # reused as provider key for easy lookup
            name="Slack Bot Token",
            provider="slack",
            description="Bot token with chat:write and channels:history scopes",
            scopes=("chat:write", "channels:history"),
            fields=(
                TemplateField(
                    key="secret",
                    label="Bot Token",
                    description="xoxb token issued by Slack",
                    validator=_require_prefix("xoxb-"),
                    secret=True,
                ),
                TemplateField(
                    key="signing_secret",
                    label="Signing Secret",
                    description="Used for webhook request validation",
                    secret=True,
                ),
            ),
            rotation_days=60,
        )
    )

    registry.register(
        CredentialTemplate(
            slug="openai",
            name="OpenAI API Key",
            provider="openai",
            description="API key for OpenAI completions and chat APIs",
            scopes=("ai:invoke",),
            fields=(
                TemplateField(
                    key="secret",
                    label="API Key",
                    description="sk- token",
                    validator=_require_prefix("sk-"),
                    secret=True,
                ),
                TemplateField(
                    key="organization",
                    label="Organization ID",
                    description="Optional org identifier to scope usage",
                    required=False,
                ),
            ),
            rotation_days=90,
        )
    )

    registry.register(
        CredentialTemplate(
            slug="postgresql",
            name="PostgreSQL Connection",
            provider="postgresql",
            description="Connection string for PostgreSQL databases",
            scopes=("storage:postgresql",),
            fields=(
                TemplateField(
                    key="secret",
                    label="Connection URL",
                    description="postgresql://user:password@host:port/database",
                    validator=_require_prefix("postgresql://"),
                    secret=True,
                ),
            ),
            rotation_days=120,
        )
    )

    return registry


def _require_prefix(prefix: str) -> FieldValidator:
    """Return a validator ensuring values start with the prefix."""

    def _validator(value: str) -> None:
        if not value.startswith(prefix):
            msg = f"Value must start with '{prefix}'"
            raise ValueError(msg)

    return _validator


__all__ = [
    "CredentialTemplate",
    "GovernanceAlertKind",
    "GovernanceAlertLevel",
    "SecretGovernanceAlert",
    "TemplateField",
    "TemplateRegistry",
    "build_default_registry",
]
