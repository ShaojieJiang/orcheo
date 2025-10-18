"""Tests covering credential templates and governance workflows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialScope,
    OAuthTokenSecrets,
)
from orcheo.vault import InMemoryCredentialVault
from orcheo.vault.templates import (
    CredentialTemplate,
    CredentialTemplateField,
    CredentialTemplateRegistry,
    SecretGovernanceAlert,
    builtin_templates,
    governance_audit,
)


@pytest.fixture()
def vault() -> InMemoryCredentialVault:
    return InMemoryCredentialVault(cipher=AesGcmCredentialCipher(key="templates"))


def test_issue_credential_from_template(vault: InMemoryCredentialVault) -> None:
    registry = CredentialTemplateRegistry(templates={})
    registry.register(
        CredentialTemplate(
            name="Slack Bot",
            provider="slack",
            scopes=["chat:write"],
            fields=[
                CredentialTemplateField(
                    key="secret",
                    label="Bot token",
                    secret=True,
                ),
            ],
        )
    )

    credential_id, alerts = registry.issue_from_provider(
        "slack",
        vault,
        actor="alice",
        secret="xoxb-token",
        workflow_id=uuid4(),
    )

    assert alerts  # health is unknown until validation occurs
    stored = vault.reveal_secret(credential_id=credential_id)
    assert stored == "xoxb-token"


def test_missing_required_fields_raises(vault: InMemoryCredentialVault) -> None:
    template = CredentialTemplate(
        name="Custom",
        provider="custom",
        fields=[
            CredentialTemplateField(
                key="secret",
                label="Secret",
                secret=True,
            ),
            CredentialTemplateField(
                key="project_id",
                label="Project id",
            ),
        ],
    )

    with pytest.raises(ValueError, match="Missing required fields: Project id"):
        template.issue(vault, actor="bob", secret="token")


def test_oauth_template_sets_expiration(vault: InMemoryCredentialVault) -> None:
    template = CredentialTemplate(
        name="OpenAI OAuth",
        provider="openai",
        kind="oauth",
        fields=[
            CredentialTemplateField(
                key="refresh_token",
                label="Refresh token",
                secret=True,
            )
        ],
        default_token_ttl_hours=1,
        governance_window_hours=2,
    )
    workflow_id = uuid4()

    credential_id, alerts = template.issue(
        vault,
        actor="system",
        secret="refresh-token",
        workflow_id=workflow_id,
    )

    metadata = next(
        item
        for item in vault.list_credentials(
            context=CredentialAccessContext(workflow_id=workflow_id)
        )
        if item.id == credential_id
    )
    assert metadata.oauth_tokens is not None
    assert metadata.oauth_tokens.expires_at is not None
    assert metadata.oauth_tokens.expires_at > datetime.now(tz=UTC)
    # Governance window should raise an alert because expiration is within 2 hours
    assert any(alert.severity == "critical" for alert in alerts), (
        "expected governance alert for imminent expiration"
    )


def test_governance_audit_detects_expiring_credentials(
    vault: InMemoryCredentialVault,
) -> None:
    registry = builtin_templates()
    workflow_id = uuid4()
    metadata = vault.create_credential(
        name="OpenAI",
        provider="openai",
        scopes=["responses.read"],
        secret="placeholder",
        actor="system",
        scope=CredentialScope.for_workflows(workflow_id),
        kind="oauth",
    )
    context = CredentialAccessContext(workflow_id=workflow_id)
    tokens = OAuthTokenSecrets(
        access_token="access",
        refresh_token="refresh",
        expires_at=datetime.now(tz=UTC) + timedelta(hours=4),
    )
    vault.update_oauth_tokens(
        credential_id=metadata.id,
        tokens=tokens,
        actor="system",
        context=context,
    )
    # mutate to near expiry for audit
    near_expiry = datetime.now(tz=UTC) + timedelta(hours=1)
    vault.update_oauth_tokens(
        credential_id=metadata.id,
        tokens=metadata.reveal_oauth_tokens(vault.cipher).model_copy(  # type: ignore[union-attr]
            update={"expires_at": near_expiry}
        ),
        actor="system",
        context=context,
    )

    alerts = list(
        governance_audit(
            vault,
            registry=registry,
            workflow_id=workflow_id,
        )
    )
    assert alerts
    assert all(isinstance(alert, SecretGovernanceAlert) for alert in alerts)
