"""Credential template definitions used by the credential vault."""

from __future__ import annotations
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pydantic import Field, field_validator
from orcheo.models.workflow import (
    CredentialHealthStatus,
    CredentialKind,
    CredentialMetadata,
    OrcheoBaseModel,
)


class CredentialTemplateField(OrcheoBaseModel):
    """Schema describing an input required to issue a credential."""

    name: str
    label: str
    description: str | None = None
    required: bool = True
    secret: bool = True
    pattern: str | None = Field(
        default=None,
        description="Optional regular expression used to validate field values.",
    )
    example: str | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not value:
            msg = "Template field name cannot be empty"
            raise ValueError(msg)
        return value

    def validate_value(self, value: str | None) -> str:
        """Validate and normalize an inbound field value."""
        if value is None:
            if self.required:
                msg = f"Field '{self.name}' is required"
                raise ValueError(msg)
            return ""
        candidate = value.strip()
        if self.required and not candidate:
            msg = f"Field '{self.name}' is required"
            raise ValueError(msg)
        if self.pattern and candidate and not re.fullmatch(self.pattern, candidate):
            msg = f"Field '{self.name}' must match pattern {self.pattern!r}"
            raise ValueError(msg)
        return candidate


class CredentialGovernanceAlert(OrcheoBaseModel):
    """Represents a governance signal emitted during credential issuance."""

    severity: str = Field(pattern=r"^(info|warning|critical)$")
    message: str


class CredentialTemplate(OrcheoBaseModel):
    """Describes a credential template that can be issued by the vault."""

    provider: str
    display_name: str
    description: str
    kind: CredentialKind = Field(default=CredentialKind.SECRET)
    scopes: list[str] = Field(default_factory=list)
    fields: list[CredentialTemplateField] = Field(default_factory=list)
    rotate_after_days: int | None = Field(
        default=None, gt=0, description="Number of days before rotation warning"
    )
    governance_checks: list[str] = Field(default_factory=list)

    def issue(
        self,
        *,
        values: Mapping[str, str],
        actor: str,
        secret_factory: Callable[[Mapping[str, str]], str],
        vault_create: Callable[..., CredentialMetadata],
    ) -> tuple[CredentialMetadata, list[CredentialGovernanceAlert]]:
        """Issue a credential using the provided factory hooks."""
        normalized: dict[str, str] = {}
        for field in self.fields:
            supplied = values.get(field.name)
            normalized[field.name] = field.validate_value(supplied)
        secret = secret_factory(normalized)
        metadata = vault_create(
            name=f"{self.display_name} Credential",
            provider=self.provider,
            scopes=self.scopes,
            secret=secret,
            actor=actor,
            kind=self.kind,
        )
        alerts = self._evaluate_governance(metadata)
        return metadata, alerts

    def _evaluate_governance(
        self, metadata: CredentialMetadata
    ) -> list[CredentialGovernanceAlert]:
        """Return governance alerts based on the template configuration."""
        alerts: list[CredentialGovernanceAlert] = []
        if self.rotate_after_days is not None:
            threshold = metadata.created_at + timedelta(days=self.rotate_after_days)
            if threshold <= datetime.now(tz=UTC):
                alerts.append(
                    CredentialGovernanceAlert(
                        severity="warning",
                        message=(
                            f"Credential '{metadata.name}' should be rotated;"
                            " rotation interval exceeded"
                        ),
                    )
                )
        for check in self.governance_checks:
            alerts.append(
                CredentialGovernanceAlert(
                    severity="info",
                    message=check,
                )
            )
        if metadata.health.status is CredentialHealthStatus.UNHEALTHY:
            alerts.append(
                CredentialGovernanceAlert(
                    severity="critical",
                    message=(f"Credential '{metadata.name}' reported unhealthy status"),
                )
            )
        return alerts


class CredentialTemplateCatalog(OrcheoBaseModel):
    """Collection of credential templates grouped by provider slug."""

    templates: dict[str, CredentialTemplate] = Field(default_factory=dict)

    def register(self, template: CredentialTemplate) -> None:
        """Register a template in the catalog."""
        key = template.provider.lower()
        if key in self.templates:
            msg = f"Template already registered for provider '{template.provider}'"
            raise ValueError(msg)
        self.templates[key] = template

    def get(self, provider: str) -> CredentialTemplate:
        """Return a template by provider slug."""
        key = provider.lower()
        try:
            return self.templates[key]
        except KeyError as exc:  # pragma: no cover - defensive
            msg = f"No template registered for provider '{provider}'"
            raise KeyError(msg) from exc

    def issue(
        self,
        provider: str,
        *,
        values: Mapping[str, str],
        actor: str,
        secret_factory: Callable[[Mapping[str, str]], str],
        vault_create: Callable[..., CredentialMetadata],
    ) -> tuple[CredentialMetadata, list[CredentialGovernanceAlert]]:
        """Issue a credential using the named provider template."""
        template = self.get(provider)
        return template.issue(
            values=values,
            actor=actor,
            secret_factory=secret_factory,
            vault_create=vault_create,
        )

    def as_list(self) -> list[CredentialTemplate]:
        """Return templates sorted by provider for stable API responses."""
        return [self.templates[key] for key in sorted(self.templates)]


def default_secret_factory(values: Mapping[str, str]) -> str:
    """Return a JSON-like secret string for templated credentials."""
    # We avoid importing json to keep the payload deterministic for tests.
    serialized = ",".join(f"{key}={values[key]}" for key in sorted(values))
    return serialized


def build_default_template_catalog() -> CredentialTemplateCatalog:
    """Return the default catalog of credential templates."""
    catalog = CredentialTemplateCatalog()
    catalog.register(
        CredentialTemplate(
            provider="slack",
            display_name="Slack Bot Token",
            description="Slack bot token used to post workflow notifications.",
            scopes=["chat:write", "chat:write.public"],
            fields=[
                CredentialTemplateField(
                    name="bot_token",
                    label="Bot User OAuth Token",
                    pattern=r"xoxb-[0-9A-Za-z-]+",
                    example="xoxb-0000-example",
                ),
                CredentialTemplateField(
                    name="signing_secret",
                    label="Signing Secret",
                    pattern=r"[0-9A-Za-z]{16,}",
                    example="abcd1234efgh5678",
                ),
            ],
            rotate_after_days=90,
            governance_checks=[
                "Alert security when Slack app scopes change.",
            ],
        )
    )
    catalog.register(
        CredentialTemplate(
            provider="telegram",
            display_name="Telegram Bot",
            description="Telegram bot API token for sending chat updates.",
            scopes=["messages:send"],
            fields=[
                CredentialTemplateField(
                    name="bot_token",
                    label="Bot Token",
                    pattern=r"[0-9]+:[A-Za-z0-9_-]+",
                    example="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                )
            ],
            rotate_after_days=180,
        )
    )
    catalog.register(
        CredentialTemplate(
            provider="http_basic",
            display_name="HTTP Basic Auth",
            description="Username/password used to authenticate HTTP requests.",
            scopes=["http:request"],
            fields=[
                CredentialTemplateField(
                    name="username",
                    label="Username",
                    required=True,
                    secret=False,
                ),
                CredentialTemplateField(
                    name="password",
                    label="Password",
                ),
            ],
            governance_checks=[
                "Verify password manager rotation policy is configured.",
            ],
        )
    )
    catalog.register(
        CredentialTemplate(
            provider="openai_api",
            display_name="OpenAI API Key",
            description="API key for invoking OpenAI models via Orcheo nodes.",
            scopes=["ai:invoke"],
            fields=[
                CredentialTemplateField(
                    name="api_key",
                    label="OpenAI API Key",
                    pattern=r"sk-[A-Za-z0-9]{32,}",
                )
            ],
            rotate_after_days=120,
            governance_checks=[
                "Notify owners when API usage exceeds quota thresholds.",
            ],
        )
    )
    return catalog


__all__ = [
    "CredentialGovernanceAlert",
    "CredentialTemplate",
    "CredentialTemplateCatalog",
    "CredentialTemplateField",
    "build_default_template_catalog",
    "default_secret_factory",
]
