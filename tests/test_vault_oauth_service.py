"""Tests for the OAuth credential service refresh and validation flows."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialKind,
    CredentialScope,
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
