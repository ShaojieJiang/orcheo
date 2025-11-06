"""Tests for credential operations backed by InMemoryCredentialVault."""

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
    GovernanceAlertKind,
    OAuthTokenSecrets,
    SecretGovernanceAlertSeverity,
)
from orcheo.vault import (
    CredentialNotFoundError,
    InMemoryCredentialVault,
)


def test_vault_updates_oauth_tokens_and_health() -> None:
    cipher = AesGcmCredentialCipher(key="oauth-test-key")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    context = CredentialAccessContext(workflow_id=workflow_id)
    expiry = datetime.now(tz=UTC) + timedelta(minutes=30)

    metadata = vault.create_credential(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        secret="client-secret",
        actor="alice",
        scope=CredentialScope.for_workflows(workflow_id),
        kind=CredentialKind.OAUTH,
        oauth_tokens=OAuthTokenSecrets(
            access_token="access-1",
            refresh_token="refresh-1",
            expires_at=expiry,
        ),
    )

    tokens = metadata.reveal_oauth_tokens(cipher=cipher)
    assert tokens is not None and tokens.refresh_token == "refresh-1"

    updated = vault.update_oauth_tokens(
        credential_id=metadata.id,
        tokens=OAuthTokenSecrets(access_token="access-2"),
        actor="validator",
        context=context,
    )
    rotated_tokens = updated.reveal_oauth_tokens(cipher=cipher)
    assert rotated_tokens is not None
    assert rotated_tokens.access_token == "access-2"
    assert rotated_tokens.refresh_token is None
    assert rotated_tokens.expires_at is None

    healthy = vault.mark_health(
        credential_id=metadata.id,
        status=CredentialHealthStatus.HEALTHY,
        reason=None,
        actor="validator",
        context=context,
    )
    assert healthy.health.status is CredentialHealthStatus.HEALTHY

    masked = vault.describe_credentials(context=context)[0]
    assert masked["oauth_tokens"]["has_access_token"] is True
    assert masked["oauth_tokens"]["has_refresh_token"] is False
    assert masked["health"]["status"] == CredentialHealthStatus.HEALTHY.value


def test_vault_cipher_property_access() -> None:
    cipher = AesGcmCredentialCipher(key="cipher-property-test")
    vault = InMemoryCredentialVault(cipher=cipher)
    assert vault.cipher is cipher
    assert vault.cipher.algorithm == "aes256-gcm.v1"


def test_delete_credential_removes_credential_and_alerts() -> None:
    cipher = AesGcmCredentialCipher(key="delete-credential")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    context = CredentialAccessContext(workflow_id=workflow_id)

    metadata = vault.create_credential(
        name="Service",
        provider="service",
        scopes=["read"],
        secret="secret",
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
    )

    vault.record_alert(
        kind=GovernanceAlertKind.TOKEN_EXPIRING,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="expiring",
        actor="ops",
        credential_id=metadata.id,
        context=context,
    )

    assert len(vault.list_credentials(context=context)) == 1
    assert len(vault.list_alerts(context=context)) == 1

    vault.delete_credential(metadata.id, context=context)

    assert len(vault.list_credentials(context=context)) == 0
    assert len(vault.list_alerts(context=context)) == 0


def test_inmemory_remove_credential_missing() -> None:
    vault = InMemoryCredentialVault()
    with pytest.raises(CredentialNotFoundError):
        vault._remove_credential(uuid4())
