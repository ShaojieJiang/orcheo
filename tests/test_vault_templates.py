"""Tests for credential template registry and governance alerts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialKind,
)
from orcheo.vault import InMemoryCredentialVault
from orcheo.vault.templates import (
    CredentialTemplate,
    CredentialTemplateRegistry,
)


def _create_vault() -> InMemoryCredentialVault:
    return InMemoryCredentialVault(cipher=AesGcmCredentialCipher(key="template-key"))


def test_template_instantiation_records_assignment() -> None:
    registry = CredentialTemplateRegistry()
    registry.register(
        CredentialTemplate(
            slug="slack-bot",
            provider="slack",
            description="Slack OAuth",  # noqa: ERA001 - fixture description
            default_scopes=("chat:write",),
            kind=CredentialKind.OAUTH,
            requires_refresh_token=True,
            rotation_interval_days=30,
        )
    )
    vault = _create_vault()
    workflow_id = uuid4()
    tokens = registry.get("slack-bot").build_oauth_tokens(
        access_token="token",
        refresh_token="refresh",
        expires_in_seconds=3600,
    )

    metadata = registry.instantiate(
        "slack-bot",
        vault=vault,
        workflow_id=workflow_id,
        name="Slack Bot",
        secret="client-secret",
        actor="alice",
        oauth_tokens=tokens,
    )

    stored = vault.list_credentials(
        context=CredentialAccessContext(workflow_id=workflow_id)
    )
    assert stored and stored[0].id == metadata.id


def test_generate_alerts_detects_rotation_and_refresh_token() -> None:
    registry = CredentialTemplateRegistry()
    template = CredentialTemplate(
        slug="slack-bot",
        provider="slack",
        description="Slack OAuth",
        default_scopes=("chat:write",),
        kind=CredentialKind.OAUTH,
        requires_refresh_token=True,
        rotation_interval_days=7,
    )
    registry.register(template)
    vault = _create_vault()
    workflow_id = uuid4()
    metadata = registry.instantiate(
        "slack-bot",
        vault=vault,
        workflow_id=workflow_id,
        name="Slack Bot",
        secret="client-secret",
        actor="alice",
    )
    # simulate stale rotation and health failure
    metadata.last_rotated_at = datetime.now(tz=UTC) - timedelta(days=30)
    vault._persist_metadata(metadata)  # type: ignore[attr-defined]
    vault.mark_health(
        credential_id=metadata.id,
        status=CredentialHealthStatus.UNHEALTHY,
        reason="failure",
        actor="ops",
        context=CredentialAccessContext(workflow_id=workflow_id),
    )

    alerts = registry.generate_alerts(
        vault=vault,
        workflow_id=workflow_id,
        now=datetime.now(tz=UTC),
    )

    messages = {alert.message for alert in alerts}
    assert any("Refresh token missing" in message for message in messages)
    assert any("rotation overdue" in message for message in messages)
    assert any("health reported unhealthy" in message for message in messages)

