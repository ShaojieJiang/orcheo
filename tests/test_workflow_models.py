"""Tests for workflow and credential domain models."""

from __future__ import annotations
from base64 import b64encode
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4
import pytest
from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialCipher,
    CredentialHealthStatus,
    CredentialIssuancePolicy,
    CredentialKind,
    CredentialMetadata,
    CredentialScope,
    CredentialTemplate,
    EncryptionEnvelope,
    FernetCredentialCipher,
    GovernanceAlertKind,
    OAuthTokenSecrets,
    SecretGovernanceAlert,
    SecretGovernanceAlertSeverity,
    Workflow,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowVersion,
)
from orcheo.models.workflow import OAuthTokenPayload


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


def test_credential_template_scope_normalization_handles_duplicates() -> None:
    template = CredentialTemplate.create(
        name="API",
        provider="service",
        scopes=["read", "read", "  write  ", ""],
        actor="alice",
    )

    assert template.scopes == ["read", "write"]


def test_credential_metadata_encrypts_and_redacts_secrets() -> None:
    cipher = AesGcmCredentialCipher(key="super-secret-key", key_id="k1")

    metadata = CredentialMetadata.create(
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
    assert metadata.kind is CredentialKind.SECRET
    assert metadata.health.status is CredentialHealthStatus.UNKNOWN

    metadata.rotate_secret(secret="rotated-token", cipher=cipher, actor="bob")
    assert metadata.reveal(cipher=cipher) == "rotated-token"
    assert metadata.audit_log[-1].action == "credential_rotated"
    assert metadata.health.status is CredentialHealthStatus.UNKNOWN

    redacted = metadata.redact()
    assert "ciphertext" not in redacted["encryption"]
    assert redacted["encryption"]["algorithm"] == cipher.algorithm
    assert redacted["encryption"]["key_id"] == cipher.key_id
    assert redacted["scope"] == {
        "workflow_ids": [],
        "workspace_ids": [],
        "roles": [],
    }
    assert redacted["kind"] == "secret"
    assert redacted["oauth_tokens"] is None
    assert redacted["health"]["status"] == CredentialHealthStatus.UNKNOWN.value

    wrong_cipher = AesGcmCredentialCipher(key="other-key", key_id="k1")
    with pytest.raises(ValueError):
        metadata.reveal(cipher=wrong_cipher)

    mismatched_cipher = AesGcmCredentialCipher(key="super-secret-key", key_id="k2")
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


def test_credential_metadata_oauth_token_management() -> None:
    cipher = AesGcmCredentialCipher(key="oauth-secret")
    expiry = datetime.now(tz=UTC) + timedelta(hours=1)
    metadata = CredentialMetadata.create(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        secret="client-secret",
        cipher=cipher,
        actor="alice",
        kind=CredentialKind.OAUTH,
        oauth_tokens=OAuthTokenSecrets(
            access_token="access-1",
            refresh_token="refresh-1",
            expires_at=expiry,
        ),
    )

    tokens = metadata.reveal_oauth_tokens(cipher=cipher)
    assert tokens is not None
    assert tokens.access_token == "access-1"
    assert tokens.refresh_token == "refresh-1"
    assert tokens.expires_at == expiry

    metadata.update_oauth_tokens(
        cipher=cipher,
        tokens=OAuthTokenSecrets(access_token="access-2", expires_at=None),
        actor="validator",
    )
    rotated_tokens = metadata.reveal_oauth_tokens(cipher=cipher)
    assert rotated_tokens is not None
    assert rotated_tokens.access_token == "access-2"
    assert rotated_tokens.refresh_token is None
    assert rotated_tokens.expires_at is None

    metadata.mark_health(
        status=CredentialHealthStatus.HEALTHY,
        reason=None,
        actor="validator",
    )
    assert metadata.health.status is CredentialHealthStatus.HEALTHY
    assert metadata.health.failure_reason is None
    assert metadata.health.last_checked_at is not None

    redacted = metadata.redact()
    assert redacted["kind"] == "oauth"
    assert redacted["oauth_tokens"]["has_access_token"] is True
    assert redacted["oauth_tokens"]["has_refresh_token"] is False
    assert redacted["health"]["status"] == CredentialHealthStatus.HEALTHY.value

    metadata.health.update(status=CredentialHealthStatus.HEALTHY)
    metadata.rotate_secret(secret="new-secret", cipher=cipher, actor="ops")
    assert metadata.health.status is CredentialHealthStatus.UNKNOWN

    metadata.update_oauth_tokens(cipher=cipher, tokens=None, actor="ops")
    assert metadata.reveal_oauth_tokens(cipher=cipher) is None


def test_oauth_token_models_normalize_naive_expiry() -> None:
    cipher = AesGcmCredentialCipher(key="normalize")
    naive = datetime(2025, 1, 1, 12, 0, 0)

    secrets = OAuthTokenSecrets(expires_at=naive)
    assert secrets.expires_at is not None
    assert secrets.expires_at.tzinfo is UTC

    payload = OAuthTokenPayload.from_secrets(cipher=cipher, secrets=secrets)
    assert payload.expires_at is not None
    assert payload.expires_at.tzinfo is UTC

    empty_payload = OAuthTokenPayload.from_secrets(cipher=cipher, secrets=None)
    assert empty_payload.access_token is None
    assert empty_payload.refresh_token is None
    assert empty_payload.expires_at is None

    direct_payload = OAuthTokenPayload(expires_at=naive)
    assert direct_payload.expires_at is not None
    assert direct_payload.expires_at.tzinfo is UTC


def test_update_oauth_tokens_rejects_non_oauth_credentials() -> None:
    cipher = AesGcmCredentialCipher(key="non-oauth")
    metadata = CredentialMetadata.create(
        name="Webhook Secret",
        provider="internal",
        scopes=[],
        secret="secret",
        cipher=cipher,
        actor="ops",
        kind=CredentialKind.SECRET,
    )

    with pytest.raises(ValueError):
        metadata.update_oauth_tokens(cipher=cipher, tokens=None)


def test_credential_scope_allows_multiple_constraints() -> None:
    workflow_id = uuid4()
    workspace_id = uuid4()

    unrestricted = CredentialScope.unrestricted()
    assert unrestricted.is_unrestricted()
    assert unrestricted.allows(CredentialAccessContext())

    workflow_scope = CredentialScope.for_workflows(workflow_id, workflow_id)
    assert workflow_scope.allows(CredentialAccessContext(workflow_id=workflow_id))
    assert not workflow_scope.allows(CredentialAccessContext(workflow_id=uuid4()))

    workspace_scope = CredentialScope.for_workspaces(workspace_id)
    assert workspace_scope.allows(CredentialAccessContext(workspace_id=workspace_id))
    assert not workspace_scope.allows(CredentialAccessContext())
    assert workspace_scope.scope_hint() == str(workspace_id)

    combined = CredentialScope(
        workflow_ids=[workflow_id],
        workspace_ids=[workspace_id],
        roles=["Admin", "admin"],
    )
    context = CredentialAccessContext(
        workflow_id=workflow_id,
        workspace_id=workspace_id,
        roles=["operator", "Admin"],
    )
    assert combined.allows(context)
    assert combined.scope_hint() == str(workflow_id)
    assert not combined.is_unrestricted()

    mismatched_roles = CredentialAccessContext(
        workflow_id=workflow_id,
        workspace_id=workspace_id,
        roles=["viewer"],
    )
    assert not combined.allows(mismatched_roles)

    role_only_scope = CredentialScope.for_roles("Admin", "Admin", " ")
    assert role_only_scope.scope_hint() == "admin"
    assert role_only_scope.roles == ["admin"]
    assert not role_only_scope.allows(CredentialAccessContext())

    normalized_context = CredentialAccessContext(roles=["Admin", "admin", " "])
    assert normalized_context.roles == ["admin"]


def test_fernet_cipher_round_trip_and_algorithm_mismatch() -> None:
    cipher = FernetCredentialCipher(key="my-fernet-key", key_id="fernet")

    envelope = cipher.encrypt("top-secret")

    assert envelope.algorithm == cipher.algorithm
    assert envelope.key_id == cipher.key_id
    assert cipher.decrypt(envelope) == "top-secret"
    assert envelope.decrypt(cipher) == "top-secret"

    aes_cipher = AesGcmCredentialCipher(key="another-key", key_id="fernet")
    with pytest.raises(ValueError, match="Cipher algorithm mismatch"):
        envelope.decrypt(aes_cipher)


def test_aes_cipher_rejects_short_payloads() -> None:
    cipher = AesGcmCredentialCipher(key="short-payload-key", key_id="k1")
    bad_payload = b64encode(b"too-short").decode("utf-8")
    envelope = EncryptionEnvelope(
        algorithm=cipher.algorithm,
        key_id=cipher.key_id,
        ciphertext=bad_payload,
    )

    with pytest.raises(ValueError, match="too short"):
        cipher.decrypt(envelope)


def test_credential_issuance_policy_rotation_detection() -> None:
    policy = CredentialIssuancePolicy(rotation_period_days=7)
    now = datetime.now(tz=UTC)

    assert not policy.requires_rotation(last_rotated_at=now - timedelta(days=6))
    assert policy.requires_rotation(last_rotated_at=now - timedelta(days=8))
    assert not policy.requires_rotation(last_rotated_at=None)


def test_credential_template_instantiation_and_audit() -> None:
    cipher = AesGcmCredentialCipher(key="template-key")
    template = CredentialTemplate.create(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        actor="alice",
        description="Slack bot",
        scope=CredentialScope.for_roles("admin"),
        kind=CredentialKind.OAUTH,
        issuance_policy=CredentialIssuancePolicy(
            require_refresh_token=True, rotation_period_days=30
        ),
    )

    metadata = template.instantiate_metadata(
        name="Slack Prod",
        secret="client-secret",
        cipher=cipher,
        actor="alice",
        scopes=["chat:write", "chat:read"],
        oauth_tokens=OAuthTokenSecrets(access_token="tok", refresh_token="ref"),
    )

    assert metadata.template_id == template.id
    assert metadata.name == "Slack Prod"
    assert metadata.scopes == ["chat:write", "chat:read"]
    assert metadata.reveal(cipher=cipher) == "client-secret"
    template.record_issuance(actor="alice", credential_id=metadata.id)
    assert template.audit_log[-1].action == "credential_issued"


def test_secret_governance_alert_acknowledgement() -> None:
    scope = CredentialScope.unrestricted()
    alert = SecretGovernanceAlert.create(
        scope=scope,
        kind=GovernanceAlertKind.TOKEN_EXPIRING,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="Token nearing expiry",
        actor="bot",
        credential_id=uuid4(),
    )

    assert not alert.is_acknowledged
    alert.acknowledge(actor="alice")
    assert alert.is_acknowledged
    assert alert.acknowledged_by == "alice"
    assert alert.redact()["kind"] == GovernanceAlertKind.TOKEN_EXPIRING.value


def test_secret_governance_alert_acknowledge_is_idempotent() -> None:
    alert = SecretGovernanceAlert.create(
        scope=CredentialScope.unrestricted(),
        kind=GovernanceAlertKind.VALIDATION_FAILED,
        severity=SecretGovernanceAlertSeverity.CRITICAL,
        message="failed",
        actor="ops",
    )

    alert.acknowledge(actor="ops")
    acknowledged_at = alert.acknowledged_at

    alert.acknowledge(actor="ops")

    assert alert.acknowledged_at == acknowledged_at
    assert alert.audit_log[-1].action == "alert_acknowledged"
