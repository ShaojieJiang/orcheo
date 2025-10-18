"""Tests for the OAuth credential service refresh and validation flows."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialIssuancePolicy,
    CredentialHealthStatus,
    CredentialKind,
    CredentialScope,
    GovernanceAlertKind,
    OAuthTokenSecrets,
)
from orcheo.vault import InMemoryCredentialVault
from orcheo.vault.oauth import (
    CredentialHealthError,
    OAuthCredentialService,
    OAuthProvider,
    OAuthValidationResult,
)


class SuccessfulProvider(OAuthProvider):
    """Provider that always refreshes tokens and reports healthy."""

    def __init__(self) -> None:
        self.refresh_calls = 0
        self.validate_calls = 0

    async def refresh_tokens(self, metadata, tokens):  # type: ignore[override]
        self.refresh_calls += 1
        return OAuthTokenSecrets(
            access_token="refreshed-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(tz=UTC) + timedelta(hours=2),
        )

    async def validate_tokens(self, metadata, tokens):  # type: ignore[override]
        self.validate_calls += 1
        return OAuthValidationResult(status=CredentialHealthStatus.HEALTHY)


class FailingProvider(OAuthProvider):
    """Provider that always reports unhealthy credentials."""

    async def refresh_tokens(self, metadata, tokens):  # type: ignore[override]
        return tokens

    async def validate_tokens(self, metadata, tokens):  # type: ignore[override]
        return OAuthValidationResult(
            status=CredentialHealthStatus.UNHEALTHY,
            failure_reason="expired",
        )


@pytest.mark.asyncio()
async def test_oauth_service_refreshes_and_marks_health() -> None:
    cipher = AesGcmCredentialCipher(key="service-key")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    context = CredentialAccessContext(workflow_id=workflow_id)
    vault.create_credential(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        secret="client-secret",
        actor="alice",
        scope=CredentialScope.for_workflows(workflow_id),
        kind=CredentialKind.OAUTH,
        oauth_tokens=OAuthTokenSecrets(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(tz=UTC) + timedelta(minutes=5),
        ),
    )

    service = OAuthCredentialService(
        vault,
        token_ttl_seconds=600,
        providers={"slack": SuccessfulProvider()},
    )

    report = await service.ensure_workflow_health(workflow_id, actor="scheduler")
    assert report.is_healthy
    assert service.is_workflow_healthy(workflow_id)
    assert report.results[0].status is CredentialHealthStatus.HEALTHY
    assert report.results[0].last_checked_at is not None

    stored = vault.list_credentials(context=context)[0]
    tokens = stored.reveal_oauth_tokens(cipher=cipher)
    assert tokens is not None and tokens.access_token == "refreshed-token"
    assert vault.list_alerts() == []


@pytest.mark.asyncio()
async def test_oauth_service_records_unhealthy_credentials() -> None:
    cipher = AesGcmCredentialCipher(key="service-key-2")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    vault.create_credential(
        name="Feedly",
        provider="feedly",
        scopes=["read"],
        secret="client-secret",
        actor="alice",
        scope=CredentialScope.for_workflows(workflow_id),
        kind=CredentialKind.OAUTH,
        oauth_tokens=OAuthTokenSecrets(access_token="initial"),
    )

    service = OAuthCredentialService(
        vault,
        token_ttl_seconds=600,
        providers={"feedly": FailingProvider()},
    )

    report = await service.ensure_workflow_health(workflow_id, actor="validator")
    assert not report.is_healthy
    assert report.failures == ["expired"]
    assert not service.is_workflow_healthy(workflow_id)

    alerts = vault.list_alerts()
    assert alerts and alerts[0].kind is GovernanceAlertKind.VALIDATION_FAILED

    with pytest.raises(CredentialHealthError):
        service.require_healthy(workflow_id)


def test_oauth_service_validates_configuration() -> None:
    vault = InMemoryCredentialVault()
    with pytest.raises(ValueError):
        OAuthCredentialService(vault, token_ttl_seconds=0)

    service = OAuthCredentialService(vault, token_ttl_seconds=60)
    with pytest.raises(ValueError):
        service.register_provider("", SuccessfulProvider())


@pytest.mark.asyncio()
async def test_oauth_service_updates_non_oauth_credentials() -> None:
    cipher = AesGcmCredentialCipher(key="non-oauth-service")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    vault.create_credential(
        name="Webhook Secret",
        provider="internal",
        scopes=[],
        secret="secret",
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
    )

    service = OAuthCredentialService(vault, token_ttl_seconds=120)
    service.require_healthy(workflow_id)  # No cached report yet.

    report = await service.ensure_workflow_health(workflow_id)
    assert report.is_healthy
    assert service.is_workflow_healthy(workflow_id)


@pytest.mark.asyncio()
async def test_oauth_service_marks_unhealthy_when_provider_missing() -> None:
    cipher = AesGcmCredentialCipher(key="missing-provider")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    vault.create_credential(
        name="Feedly",
        provider="feedly",
        scopes=["read"],
        secret="secret",
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
        kind=CredentialKind.OAUTH,
        oauth_tokens=OAuthTokenSecrets(access_token="token"),
    )

    service = OAuthCredentialService(vault, token_ttl_seconds=120)
    report = await service.ensure_workflow_health(workflow_id)
    assert not report.is_healthy
    assert "No OAuth provider" in report.failures[0]
    alerts = vault.list_alerts()
    assert alerts and alerts[0].kind is GovernanceAlertKind.VALIDATION_FAILED


def test_oauth_service_refresh_margin_logic() -> None:
    cipher = AesGcmCredentialCipher(key="refresh-logic")
    vault = InMemoryCredentialVault(cipher=cipher)
    service = OAuthCredentialService(vault, token_ttl_seconds=300)

    assert service._should_refresh(None)
    tokens_without_expiry = OAuthTokenSecrets(access_token="a")
    assert not service._should_refresh(tokens_without_expiry)
    expiring_tokens = OAuthTokenSecrets(
        access_token="a",
        expires_at=datetime.now(tz=UTC) + timedelta(minutes=2),
    )
    assert service._should_refresh(expiring_tokens)


class NoRefreshProvider(OAuthProvider):
    async def refresh_tokens(self, metadata, tokens):  # type: ignore[override]
        return None

    async def validate_tokens(self, metadata, tokens):  # type: ignore[override]
        return OAuthValidationResult(status=CredentialHealthStatus.HEALTHY)


@pytest.mark.asyncio()
async def test_oauth_service_handles_provider_without_refresh() -> None:
    cipher = AesGcmCredentialCipher(key="no-refresh")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    vault.create_credential(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        secret="client-secret",
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
        kind=CredentialKind.OAUTH,
        oauth_tokens=OAuthTokenSecrets(
            access_token="initial",
            expires_at=datetime.now(tz=UTC) + timedelta(minutes=1),
        ),
    )

    service = OAuthCredentialService(
        vault,
        token_ttl_seconds=600,
        providers={"slack": NoRefreshProvider()},
    )

    report = await service.ensure_workflow_health(workflow_id)
    assert report.is_healthy


def test_oauth_service_loads_template_for_metadata() -> None:
    cipher = AesGcmCredentialCipher(key="template-load")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    template = vault.create_template(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
        kind=CredentialKind.OAUTH,
    )
    metadata = vault.create_credential(
        name="Slack",  # type: ignore[arg-type]
        provider="slack",
        scopes=["chat:write"],
        secret="secret",
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
        kind=CredentialKind.OAUTH,
        template_id=template.id,
    )

    service = OAuthCredentialService(vault, token_ttl_seconds=600)
    context = CredentialAccessContext(workflow_id=workflow_id)
    loaded = service._load_template_for_metadata(metadata, context)

    assert loaded is not None and loaded.id == template.id


def test_oauth_service_rotation_policy_triggers_alert(monkeypatch) -> None:
    cipher = AesGcmCredentialCipher(key="rotation-policy")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    template = vault.create_template(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
        kind=CredentialKind.OAUTH,
        issuance_policy=CredentialIssuancePolicy(rotation_period_days=30),
    )
    metadata = vault.create_credential(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        secret="secret",
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
        kind=CredentialKind.OAUTH,
        template_id=template.id,
    )
    metadata.last_rotated_at = datetime.now(tz=UTC) - timedelta(days=60)
    vault._persist_metadata(metadata)

    alerts_triggered: set[GovernanceAlertKind] = set()
    recorded: list[GovernanceAlertKind] = []
    original_record_alert = vault.record_alert

    def capture_alert(**kwargs):
        recorded.append(kwargs["kind"])
        return original_record_alert(**kwargs)

    monkeypatch.setattr(vault, "record_alert", capture_alert)

    service = OAuthCredentialService(vault, token_ttl_seconds=600)
    service._apply_rotation_policy(
        template,
        metadata,
        alerts_triggered,
        context=CredentialAccessContext(workflow_id=workflow_id),
        actor_name="ops",
    )

    assert GovernanceAlertKind.ROTATION_OVERDUE in alerts_triggered
    assert recorded == [GovernanceAlertKind.ROTATION_OVERDUE]


def test_oauth_service_validates_template_policy_tokens() -> None:
    vault = InMemoryCredentialVault()
    service = OAuthCredentialService(vault, token_ttl_seconds=120)
    policy = CredentialIssuancePolicy(require_refresh_token=True)

    with pytest.raises(ValueError):
        service._validate_template_policy(policy, oauth_tokens=None)


def test_oauth_service_validate_policy_with_refresh_token() -> None:
    vault = InMemoryCredentialVault()
    service = OAuthCredentialService(vault, token_ttl_seconds=120)
    policy = CredentialIssuancePolicy(require_refresh_token=True)
    tokens = OAuthTokenSecrets(access_token="a", refresh_token="b")

    service._validate_template_policy(policy, oauth_tokens=tokens)
