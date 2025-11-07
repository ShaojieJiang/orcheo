"""Scope enforcement tests for InMemoryCredentialVault."""

from __future__ import annotations
from uuid import UUID, uuid4
import pytest
from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialKind,
    CredentialScope,
)
from orcheo.vault import (
    CredentialNotFoundError,
    InMemoryCredentialVault,
    RotationPolicyError,
    WorkflowScopeError,
)


def test_inmemory_vault_supports_shared_and_restricted_credentials() -> None:
    cipher = AesGcmCredentialCipher(key="unit-test-key")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_a, workflow_b = uuid4(), uuid4()
    context_a, context_b = (
        CredentialAccessContext(workflow_id=workflow_a),
        CredentialAccessContext(workflow_id=workflow_b),
    )

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

    assert [item.id for item in vault.list_credentials(context=context_a)] == [
        metadata.id
    ]
    assert [item.id for item in vault.list_credentials(context=context_b)] == [
        metadata.id
    ]

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

    shared_entry = vault.describe_credentials(context=context_b)[0]
    assert shared_entry["scope"]["workflow_ids"] == []
    assert shared_entry["health"]["status"] == CredentialHealthStatus.UNKNOWN.value

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

    admin_context, viewer_context = (
        CredentialAccessContext(roles=["Admin", "operator"]),
        CredentialAccessContext(roles=["viewer"]),
    )

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


def test_delete_credential_enforces_scope() -> None:
    cipher = AesGcmCredentialCipher(key="delete-scope")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()

    metadata = vault.create_credential(
        name="Restricted",
        provider="service",
        scopes=["read"],
        secret="secret",
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
    )

    with pytest.raises(WorkflowScopeError):
        vault.delete_credential(
            metadata.id,
            context=CredentialAccessContext(workflow_id=uuid4()),
        )
