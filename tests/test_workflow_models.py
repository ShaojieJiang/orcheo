"""Tests for workflow and credential domain models."""

from __future__ import annotations
from typing import Protocol
from uuid import uuid4
import pytest
from orcheo.models import (
    CredentialCipher,
    CredentialMetadata,
    EncryptionEnvelope,
    FernetCredentialCipher,
    Workflow,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowVersion,
)


def test_workflow_slug_is_derived_from_name() -> None:
    workflow = Workflow(name="My Sample Flow")

    assert workflow.slug == "my-sample-flow"
    assert workflow.audit_log == []


def test_workflow_record_event_updates_timestamp() -> None:
    workflow = Workflow(name="Demo Flow")
    original_updated_at = workflow.updated_at

    workflow.record_event(actor="alice", action="updated", metadata={"field": "name"})

    assert len(workflow.audit_log) == 1
    assert workflow.updated_at >= original_updated_at


def test_workflow_requires_name_or_slug() -> None:
    with pytest.raises(ValueError):
        Workflow(name="", slug="")


def test_workflow_tag_normalization() -> None:
    workflow = Workflow(name="Tagged", tags=["alpha", " Alpha ", "beta", ""])

    assert workflow.tags == ["alpha", "beta"]


def test_workflow_version_checksum_is_deterministic() -> None:
    graph_definition = {"nodes": [{"id": "1", "type": "start"}], "edges": []}
    version = WorkflowVersion(
        workflow_id=uuid4(),
        version=1,
        graph=graph_definition,
        created_by="alice",
    )

    checksum = version.compute_checksum()
    assert checksum == version.compute_checksum()
    version.graph["nodes"].append({"id": "2", "type": "end"})
    assert checksum != version.compute_checksum()


def test_workflow_run_state_transitions_and_audit_trail() -> None:
    run = WorkflowRun(workflow_version_id=uuid4(), triggered_by="cron")

    run.mark_started(actor="scheduler")
    assert run.status is WorkflowRunStatus.RUNNING
    assert run.started_at is not None
    assert run.audit_log[-1].action == "run_started"

    run.mark_succeeded(actor="scheduler", output={"messages": 1})
    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert run.completed_at is not None
    assert run.output_payload == {"messages": 1}
    assert run.audit_log[-1].action == "run_succeeded"

    with pytest.raises(ValueError):
        run.mark_cancelled(actor="scheduler")


def test_workflow_run_invalid_transitions_raise_errors() -> None:
    run = WorkflowRun(workflow_version_id=uuid4(), triggered_by="user")

    with pytest.raises(ValueError):
        run.mark_succeeded(actor="user")

    run.mark_started(actor="user")

    with pytest.raises(ValueError):
        run.mark_started(actor="user")

    run.mark_failed(actor="user", error="boom")

    with pytest.raises(ValueError):
        run.mark_failed(actor="user", error="boom")

    with pytest.raises(ValueError):
        run.mark_cancelled(actor="user")


def test_workflow_run_cancel_records_reason() -> None:
    run = WorkflowRun(workflow_version_id=uuid4(), triggered_by="ops")
    run.mark_started(actor="ops")
    run.mark_cancelled(actor="ops", reason="manual stop")

    assert run.status is WorkflowRunStatus.CANCELLED
    assert run.error == "manual stop"
    assert run.audit_log[-1].metadata == {"reason": "manual stop"}


def test_workflow_run_cancel_without_reason() -> None:
    run = WorkflowRun(workflow_version_id=uuid4(), triggered_by="ops")
    run.mark_started(actor="ops")
    run.mark_cancelled(actor="ops")

    assert run.error is None
    assert run.audit_log[-1].metadata == {}


def test_credential_metadata_encrypts_and_redacts_secrets() -> None:
    cipher = FernetCredentialCipher(key="super-secret-key", key_id="k1")

    metadata = CredentialMetadata.create(
        workflow_id=uuid4(),
        name="OpenAI",
        provider="openai",
        scopes=["chat:write", "chat:write"],
        secret="initial-token",
        cipher=cipher,
        actor="alice",
    )

    assert metadata.reveal(cipher=cipher) == "initial-token"
    assert metadata.scopes == ["chat:write"]
    assert metadata.last_rotated_at is not None
    assert metadata.audit_log[-1].action == "credential_created"

    metadata.rotate_secret(secret="rotated-token", cipher=cipher, actor="bob")
    assert metadata.reveal(cipher=cipher) == "rotated-token"
    assert metadata.audit_log[-1].action == "credential_rotated"

    redacted = metadata.redact()
    assert "ciphertext" not in redacted["encryption"]
    assert redacted["encryption"]["algorithm"] == cipher.algorithm
    assert redacted["encryption"]["key_id"] == cipher.key_id

    wrong_cipher = FernetCredentialCipher(key="other-key", key_id="k1")
    with pytest.raises(ValueError):
        metadata.reveal(cipher=wrong_cipher)

    mismatched_cipher = FernetCredentialCipher(key="super-secret-key", key_id="k2")
    with pytest.raises(ValueError):
        metadata.reveal(cipher=mismatched_cipher)

    class OtherCipher(Protocol):
        algorithm: str
        key_id: str

        def decrypt(
            self, envelope: EncryptionEnvelope
        ) -> str:  # pragma: no cover - protocol
            ...

    class DummyCipher:
        algorithm = "other"
        key_id = cipher.key_id

        def encrypt(self, plaintext: str) -> EncryptionEnvelope:
            raise NotImplementedError

        def decrypt(
            self, envelope: EncryptionEnvelope
        ) -> str:  # pragma: no cover - defensive
            return ""

    dummy_cipher: CredentialCipher = DummyCipher()
    with pytest.raises(ValueError):
        metadata.encryption.decrypt(dummy_cipher)
