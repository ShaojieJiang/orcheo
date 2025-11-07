"""OAuth credential service tests covering token refresh and health."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from uuid import uuid4
import pytest
from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialKind,
    CredentialScope,
    GovernanceAlertKind,
    OAuthTokenSecrets,
)
from orcheo.vault import InMemoryCredentialVault
from orcheo.vault.oauth import CredentialHealthError, OAuthCredentialService
from tests.test_vault_oauth_service_helpers import (
    FailingProvider,
    NoRefreshProvider,
    SuccessfulProvider,
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

    alerts = vault.list_alerts(context=CredentialAccessContext(workflow_id=workflow_id))
    assert alerts and alerts[0].kind is GovernanceAlertKind.VALIDATION_FAILED

    with pytest.raises(CredentialHealthError):
        service.require_healthy(workflow_id)


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
    alerts = vault.list_alerts(context=CredentialAccessContext(workflow_id=workflow_id))
    assert alerts and alerts[0].kind is GovernanceAlertKind.VALIDATION_FAILED


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
