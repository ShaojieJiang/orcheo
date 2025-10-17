"""Tests covering credential vault implementations."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from orcheo.models import AesGcmCredentialCipher
from orcheo.vault import (
    CredentialNotFoundError,
    FileCredentialVault,
    InMemoryCredentialVault,
    RotationPolicyError,
    WorkflowScopeError,
)


def test_inmemory_vault_scopes_credentials_and_masks_logs() -> None:
    cipher = AesGcmCredentialCipher(key="unit-test-key")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()

    metadata = vault.create_credential(
        workflow_id=workflow_id,
        name="OpenAI",
        provider="openai",
        scopes=["chat:write"],
        secret="initial-token",
        actor="alice",
    )

    assert (
        vault.reveal_secret(workflow_id=workflow_id, credential_id=metadata.id)
        == "initial-token"
    )

    listed = vault.list_credentials(workflow_id=workflow_id)
    assert [item.id for item in listed] == [metadata.id]

    masked = vault.describe_credentials(workflow_id=workflow_id)
    assert masked[0]["encryption"]["algorithm"] == cipher.algorithm
    assert "ciphertext" not in masked[0]["encryption"]

    unrelated = vault.list_credentials(workflow_id=uuid4())
    assert unrelated == []

    with pytest.raises(RotationPolicyError):
        vault.rotate_secret(
            workflow_id=workflow_id,
            credential_id=metadata.id,
            secret="initial-token",
            actor="security-bot",
        )

    rotated = vault.rotate_secret(
        workflow_id=workflow_id,
        credential_id=metadata.id,
        secret="rotated-token",
        actor="security-bot",
    )
    assert rotated.last_rotated_at >= metadata.last_rotated_at
    assert (
        vault.reveal_secret(workflow_id=workflow_id, credential_id=metadata.id)
        == "rotated-token"
    )

    other_workflow_id = uuid4()
    with pytest.raises(WorkflowScopeError):
        vault.reveal_secret(workflow_id=other_workflow_id, credential_id=metadata.id)

    unknown_id = UUID(int=0)
    with pytest.raises(CredentialNotFoundError):
        vault.reveal_secret(workflow_id=workflow_id, credential_id=unknown_id)
    assert vault.describe_credentials(workflow_id=uuid4()) == []


def test_file_vault_persists_credentials(tmp_path) -> None:
    cipher = AesGcmCredentialCipher(key="file-backend-key")
    vault_path = tmp_path / "vault.sqlite"

    vault = FileCredentialVault(vault_path, cipher=cipher)
    workflow_id = uuid4()
    metadata = vault.create_credential(
        workflow_id=workflow_id,
        name="Stripe",
        provider="stripe",
        scopes=["payments:write"],
        secret="sk_live_initial",
        actor="alice",
    )

    restored = FileCredentialVault(vault_path, cipher=cipher)
    assert (
        restored.reveal_secret(workflow_id=workflow_id, credential_id=metadata.id)
        == "sk_live_initial"
    )

    restored.rotate_secret(
        workflow_id=workflow_id,
        credential_id=metadata.id,
        secret="sk_live_rotated",
        actor="security-bot",
    )

    reloaded = FileCredentialVault(vault_path, cipher=cipher)
    assert (
        reloaded.reveal_secret(workflow_id=workflow_id, credential_id=metadata.id)
        == "sk_live_rotated"
    )

    listed = reloaded.list_credentials(workflow_id=workflow_id)
    assert len(listed) == 1
    assert listed[0].provider == "stripe"

    masked = reloaded.describe_credentials(workflow_id=workflow_id)
    assert masked[0]["provider"] == "stripe"
    assert "ciphertext" not in masked[0]["encryption"]

    with pytest.raises(CredentialNotFoundError):
        reloaded.reveal_secret(workflow_id=workflow_id, credential_id=uuid4())
