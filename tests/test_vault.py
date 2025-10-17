"""Tests covering credential vault implementations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialKind,
    CredentialScope,
    OAuthTokenSecrets,
)
from orcheo.vault import (
    CredentialNotFoundError,
    FileCredentialVault,
    InMemoryCredentialVault,
    RotationPolicyError,
    WorkflowScopeError,
)


def test_inmemory_vault_supports_shared_and_restricted_credentials() -> None:
    cipher = AesGcmCredentialCipher(key="unit-test-key")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_a = uuid4()
    workflow_b = uuid4()
    context_a = CredentialAccessContext(workflow_id=workflow_a)
    context_b = CredentialAccessContext(workflow_id=workflow_b)

    metadata = vault.create_credential(
        name="OpenAI",
        provider="openai",
        scopes=["chat:write"],
        secret="initial-token",
        actor="alice",
    )

    assert metadata.kind is CredentialKind.SECRET
    assert metadata.health.status is CredentialHealthStatus.UNKNOWN

    assert (
        vault.reveal_secret(credential_id=metadata.id, context=context_a)
        == "initial-token"
    )
    assert (
        vault.reveal_secret(credential_id=metadata.id, context=context_b)
        == "initial-token"
    )

    listed_a = vault.list_credentials(context=context_a)
    listed_b = vault.list_credentials(context=context_b)
    assert [item.id for item in listed_a] == [metadata.id]
    assert [item.id for item in listed_b] == [metadata.id]

    masked = vault.describe_credentials(context=context_a)
    assert masked[0]["encryption"]["algorithm"] == cipher.algorithm
    assert "ciphertext" not in masked[0]["encryption"]
    assert masked[0]["scope"]["workflow_ids"] == []
    assert masked[0]["kind"] == "secret"
    assert masked[0]["health"]["status"] == CredentialHealthStatus.UNKNOWN.value

    with pytest.raises(RotationPolicyError):
        vault.rotate_secret(
            credential_id=metadata.id,
            secret="initial-token",
            actor="security-bot",
            context=context_a,
        )

    rotated = vault.rotate_secret(
        credential_id=metadata.id,
        secret="rotated-token",
        actor="security-bot",
        context=context_a,
    )
    assert rotated.last_rotated_at >= metadata.last_rotated_at
    assert rotated.health.status is CredentialHealthStatus.UNKNOWN
    assert (
        vault.reveal_secret(credential_id=metadata.id, context=context_a)
        == "rotated-token"
    )
    assert (
        vault.reveal_secret(credential_id=metadata.id, context=context_b)
        == "rotated-token"
    )

    shared = vault.describe_credentials(context=context_b)
    assert shared[0]["scope"]["workflow_ids"] == []
    assert shared[0]["health"]["status"] == CredentialHealthStatus.UNKNOWN.value

    restricted_scope = CredentialScope.for_workflows(workflow_a)
    restricted = vault.create_credential(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        secret="slack-token",
        actor="alice",
        scope=restricted_scope,
    )

    assert (
        vault.reveal_secret(credential_id=restricted.id, context=context_a)
        == "slack-token"
    )

    with pytest.raises(WorkflowScopeError):
        vault.reveal_secret(credential_id=restricted.id, context=context_b)

    assert {item.id for item in vault.list_credentials(context=context_a)} == {
        metadata.id,
        restricted.id,
    }
    assert [item.id for item in vault.list_credentials(context=context_b)] == [
        metadata.id
    ]

    role_scope = CredentialScope.for_roles("admin")
    role_metadata = vault.create_credential(
        name="PagerDuty",
        provider="pagerduty",
        scopes=[],
        secret="pd-key",
        actor="alice",
        scope=role_scope,
    )

    admin_context = CredentialAccessContext(roles=["Admin", "operator"])
    viewer_context = CredentialAccessContext(roles=["viewer"])

    assert (
        vault.reveal_secret(credential_id=role_metadata.id, context=admin_context)
        == "pd-key"
    )

    with pytest.raises(WorkflowScopeError):
        vault.reveal_secret(credential_id=role_metadata.id, context=viewer_context)

    unknown_id = UUID(int=0)
    with pytest.raises(CredentialNotFoundError):
        vault.reveal_secret(credential_id=unknown_id, context=context_a)
    viewer_describe = vault.describe_credentials(context=viewer_context)
    assert [entry["id"] for entry in viewer_describe] == [str(metadata.id)]
    assert viewer_describe[0]["scope"]["roles"] == []


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


def test_file_vault_persists_credentials(tmp_path) -> None:
    cipher = AesGcmCredentialCipher(key="file-backend-key")
    vault_path = tmp_path / "vault.sqlite"

    vault = FileCredentialVault(vault_path, cipher=cipher)
    workflow_id = uuid4()
    workflow_context = CredentialAccessContext(workflow_id=workflow_id)
    metadata = vault.create_credential(
        name="Stripe",
        provider="stripe",
        scopes=["payments:write"],
        secret="sk_live_initial",
        actor="alice",
    )

    assert metadata.kind is CredentialKind.SECRET

    restored = FileCredentialVault(vault_path, cipher=cipher)
    assert (
        restored.reveal_secret(credential_id=metadata.id, context=workflow_context)
        == "sk_live_initial"
    )

    restored.rotate_secret(
        credential_id=metadata.id,
        secret="sk_live_rotated",
        actor="security-bot",
        context=workflow_context,
    )

    reloaded = FileCredentialVault(vault_path, cipher=cipher)
    assert (
        reloaded.reveal_secret(credential_id=metadata.id, context=workflow_context)
        == "sk_live_rotated"
    )

    listed = reloaded.list_credentials(context=workflow_context)
    assert len(listed) == 1
    assert listed[0].provider == "stripe"

    masked = reloaded.describe_credentials(context=workflow_context)
    assert masked[0]["provider"] == "stripe"
    assert "ciphertext" not in masked[0]["encryption"]
    assert masked[0]["health"]["status"] == CredentialHealthStatus.UNKNOWN.value

    with pytest.raises(CredentialNotFoundError):
        reloaded.reveal_secret(
            credential_id=uuid4(),
            context=CredentialAccessContext(workflow_id=workflow_id),
        )
