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
