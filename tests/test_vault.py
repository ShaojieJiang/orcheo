"""Tests covering credential vault implementations."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
import pytest
from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialIssuancePolicy,
    CredentialKind,
    CredentialScope,
    GovernanceAlertKind,
    OAuthTokenSecrets,
    SecretGovernanceAlertSeverity,
)
from orcheo.vault import (
    CredentialNotFoundError,
    CredentialTemplateNotFoundError,
    FileCredentialVault,
    GovernanceAlertNotFoundError,
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


def test_vault_manages_templates_and_alerts() -> None:
    cipher = AesGcmCredentialCipher(key="template-test")
    vault = InMemoryCredentialVault(cipher=cipher)

    template = vault.create_template(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        actor="alice",
        description="Slack bot",
        kind=CredentialKind.OAUTH,
        issuance_policy=CredentialIssuancePolicy(rotation_period_days=30),
    )

    templates = vault.list_templates()
    assert [item.id for item in templates] == [template.id]

    updated = vault.update_template(
        template.id,
        actor="alice",
        scopes=["chat:write", "chat:read"],
        description="Updated",
    )
    assert updated.scopes == ["chat:write", "chat:read"]
    assert updated.description == "Updated"

    fetched = vault.get_template(template_id=template.id)
    assert fetched.id == template.id

    alert = vault.record_alert(
        kind=GovernanceAlertKind.TOKEN_EXPIRING,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="Token expiring",
        actor="monitor",
        credential_id=None,
        template_id=template.id,
    )
    alerts = vault.list_alerts()
    assert alerts and alerts[0].id == alert.id

    acknowledged = vault.acknowledge_alert(alert.id, actor="alice")
    assert acknowledged.is_acknowledged

    all_alerts = vault.list_alerts(include_acknowledged=True)
    assert all_alerts[0].is_acknowledged

    vault.delete_template(template.id)
    with pytest.raises(CredentialTemplateNotFoundError):
        vault.get_template(template_id=template.id)

    with pytest.raises(GovernanceAlertNotFoundError):
        vault.acknowledge_alert(alert.id, actor="bob")


def test_vault_accepts_string_kind_and_updates_health(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    cipher = AesGcmCredentialCipher(key="file-key")
    vault_path = tmp_path_factory.mktemp("vault") / "credentials.sqlite"
    vault = FileCredentialVault(path=vault_path, cipher=cipher)

    metadata = vault.create_credential(
        name="GitHub",
        provider="github",
        scopes=["repo"],
        secret="token",
        actor="alice",
        kind="oauth",
    )

    assert metadata.kind is CredentialKind.OAUTH

    metadata = vault.update_oauth_tokens(
        credential_id=metadata.id,
        tokens=OAuthTokenSecrets(access_token="access"),
        actor="alice",
    )
    assert metadata.reveal_oauth_tokens(cipher=cipher) is not None


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


def test_template_update_tracks_all_changes() -> None:
    cipher = AesGcmCredentialCipher(key="template-update")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    template = vault.create_template(
        name="Service",  # string kind conversion exercised below
        provider="service",
        scopes=["read"],
        actor="alice",
        kind="oauth",
    )

    updated_scope = CredentialScope.for_workflows(workflow_id)
    new_policy = CredentialIssuancePolicy(
        require_refresh_token=True, rotation_period_days=90
    )
    updated = vault.update_template(
        template.id,
        actor="alice",
        name="Service Prod",
        description="prod",
        scopes=["read", "write"],
        scope=updated_scope,
        kind="secret",
        issuance_policy=new_policy,
    )

    assert updated.name == "Service Prod"
    persisted = vault.get_template(
        template_id=template.id,
        context=CredentialAccessContext(workflow_id=workflow_id),
    )
    assert persisted.issuance_policy.rotation_period_days == 90
    last_event = persisted.audit_log[-1]
    assert last_event.action == "template_updated"
    assert {
        "name",
        "description",
        "scopes",
        "scope",
        "kind",
        "issuance_policy",
    }.issubset(last_event.metadata.keys())


def test_template_update_without_changes_is_noop() -> None:
    cipher = AesGcmCredentialCipher(key="template-noop")
    vault = InMemoryCredentialVault(cipher=cipher)
    template = vault.create_template(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        actor="alice",
    )

    updated = vault.update_template(template.id, actor="alice")
    assert updated.audit_log == template.audit_log


def test_template_update_ignores_identical_payloads() -> None:
    cipher = AesGcmCredentialCipher(key="template-same")
    vault = InMemoryCredentialVault(cipher=cipher)
    template = vault.create_template(
        name="Service",
        provider="service",
        scopes=["read"],
        actor="alice",
        issuance_policy=CredentialIssuancePolicy(rotation_period_days=30),
    )

    same_policy = CredentialIssuancePolicy(
        rotation_period_days=template.issuance_policy.rotation_period_days,
        require_refresh_token=template.issuance_policy.require_refresh_token,
        expiry_threshold_minutes=template.issuance_policy.expiry_threshold_minutes,
    )

    result = vault.update_template(
        template.id,
        actor="alice",
        name=template.name,
        scopes=list(template.scopes),
        kind=template.kind,
        issuance_policy=same_policy,
    )

    assert result.audit_log == template.audit_log


def test_get_template_enforces_scope() -> None:
    cipher = AesGcmCredentialCipher(key="template-scope")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    template = vault.create_template(
        name="Restricted",
        provider="internal",
        scopes=["read"],
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
    )

    with pytest.raises(WorkflowScopeError):
        vault.get_template(
            template_id=template.id,
            context=CredentialAccessContext(workflow_id=uuid4()),
        )


def test_record_alert_updates_existing_entries() -> None:
    cipher = AesGcmCredentialCipher(key="alert-update")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    metadata = vault.create_credential(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        secret="client-secret",
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
    )

    first = vault.record_alert(
        kind=GovernanceAlertKind.TOKEN_EXPIRING,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="expires soon",
        actor="monitor",
        credential_id=metadata.id,
        context=CredentialAccessContext(workflow_id=workflow_id),
    )
    second = vault.record_alert(
        kind=GovernanceAlertKind.TOKEN_EXPIRING,
        severity=SecretGovernanceAlertSeverity.CRITICAL,
        message="expired",
        actor="monitor",
        credential_id=metadata.id,
        context=CredentialAccessContext(workflow_id=workflow_id),
    )

    assert second.id == first.id
    assert second.message == "expired"
    assert second.audit_log[-1].action == "alert_updated"


def test_record_alert_uses_template_scope() -> None:
    cipher = AesGcmCredentialCipher(key="alert-template")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    template = vault.create_template(
        name="API",
        provider="api",
        scopes=["read"],
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
    )

    alert = vault.record_alert(
        kind=GovernanceAlertKind.ROTATION_OVERDUE,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="rotate",
        actor="ops",
        template_id=template.id,
        context=CredentialAccessContext(workflow_id=workflow_id),
    )

    assert alert.scope == template.scope


def test_record_alert_skips_acknowledged_entries() -> None:
    cipher = AesGcmCredentialCipher(key="alert-skip")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    metadata = vault.create_credential(
        name="Service",
        provider="service",
        scopes=["read"],
        secret="secret",
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
    )

    alert = vault.record_alert(
        kind=GovernanceAlertKind.TOKEN_EXPIRING,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="expiring",
        actor="ops",
        credential_id=metadata.id,
        context=CredentialAccessContext(workflow_id=workflow_id),
    )
    vault.acknowledge_alert(
        alert.id,
        actor="ops",
        context=CredentialAccessContext(workflow_id=workflow_id),
    )

    refreshed = vault.record_alert(
        kind=GovernanceAlertKind.TOKEN_EXPIRING,
        severity=SecretGovernanceAlertSeverity.CRITICAL,
        message="expiring",
        actor="ops",
        credential_id=metadata.id,
        context=CredentialAccessContext(workflow_id=workflow_id),
    )

    assert refreshed.id != alert.id


def test_list_alerts_filters_by_context_and_acknowledgement() -> None:
    cipher = AesGcmCredentialCipher(key="alert-list")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    template = vault.create_template(
        name="Restricted",
        provider="service",
        scopes=["read"],
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
    )
    restricted = vault.record_alert(
        kind=GovernanceAlertKind.TOKEN_EXPIRING,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="restricted",
        actor="ops",
        template_id=template.id,
        context=CredentialAccessContext(workflow_id=workflow_id),
    )
    _global_alert = vault.record_alert(
        kind=GovernanceAlertKind.VALIDATION_FAILED,
        severity=SecretGovernanceAlertSeverity.CRITICAL,
        message="global",
        actor="ops",
    )

    filtered = vault.list_alerts(
        context=CredentialAccessContext(workflow_id=uuid4()),
        include_acknowledged=False,
    )
    assert [alert.message for alert in filtered] == ["global"]

    vault.acknowledge_alert(
        restricted.id,
        actor="ops",
        context=CredentialAccessContext(workflow_id=workflow_id),
    )
    all_alerts = vault.list_alerts(
        context=CredentialAccessContext(workflow_id=workflow_id),
        include_acknowledged=True,
    )
    assert {alert.message for alert in all_alerts} == {"restricted", "global"}


def test_list_alerts_excludes_acknowledged_by_default() -> None:
    vault = InMemoryCredentialVault()
    alert = vault.record_alert(
        kind=GovernanceAlertKind.VALIDATION_FAILED,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="failure",
        actor="ops",
    )
    vault.acknowledge_alert(alert.id, actor="ops")

    assert vault.list_alerts() == []


def test_acknowledge_alert_enforces_scope() -> None:
    cipher = AesGcmCredentialCipher(key="alert-scope")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    template = vault.create_template(
        name="Restricted",
        provider="service",
        scopes=["read"],
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
    )
    alert = vault.record_alert(
        kind=GovernanceAlertKind.ROTATION_OVERDUE,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="rotate",
        actor="ops",
        template_id=template.id,
        context=CredentialAccessContext(workflow_id=workflow_id),
    )

    with pytest.raises(WorkflowScopeError):
        vault.acknowledge_alert(alert.id, actor="ops")

    with pytest.raises(WorkflowScopeError):
        vault.acknowledge_alert(
            alert.id,
            actor="viewer",
            context=CredentialAccessContext(workflow_id=uuid4()),
        )

    acknowledged = vault.acknowledge_alert(
        alert.id,
        actor="ops",
        context=CredentialAccessContext(workflow_id=workflow_id),
    )
    assert acknowledged.is_acknowledged is True


def test_resolve_alerts_for_credential_marks_all() -> None:
    cipher = AesGcmCredentialCipher(key="alert-resolve")
    vault = InMemoryCredentialVault(cipher=cipher)
    metadata = vault.create_credential(
        name="Service",
        provider="service",
        scopes=["read"],
        secret="secret",
        actor="ops",
    )
    vault.record_alert(
        kind=GovernanceAlertKind.TOKEN_EXPIRING,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="expiring",
        actor="ops",
        credential_id=metadata.id,
    )
    vault.record_alert(
        kind=GovernanceAlertKind.ROTATION_OVERDUE,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="rotate",
        actor="ops",
        credential_id=metadata.id,
    )

    resolved = vault.resolve_alerts_for_credential(metadata.id, actor="ops")
    assert len(resolved) == 2
    assert all(alert.is_acknowledged for alert in resolved)


def test_resolve_alerts_skips_acknowledged_entries() -> None:
    vault = InMemoryCredentialVault()
    metadata = vault.create_credential(
        name="Service",
        provider="service",
        scopes=["read"],
        secret="secret",
        actor="ops",
    )
    alert_one = vault.record_alert(
        kind=GovernanceAlertKind.TOKEN_EXPIRING,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="one",
        actor="ops",
        credential_id=metadata.id,
    )
    alert_two = vault.record_alert(
        kind=GovernanceAlertKind.ROTATION_OVERDUE,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="two",
        actor="ops",
        credential_id=metadata.id,
    )
    vault.acknowledge_alert(alert_one.id, actor="ops")

    resolved = vault.resolve_alerts_for_credential(metadata.id, actor="ops")

    assert [item.id for item in resolved] == [alert_two.id]


def test_record_template_issuance_validates_scope() -> None:
    cipher = AesGcmCredentialCipher(key="issuance-scope")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    template = vault.create_template(
        name="Restricted",
        provider="service",
        scopes=["read"],
        actor="ops",
        scope=CredentialScope.for_workflows(workflow_id),
    )

    with pytest.raises(WorkflowScopeError):
        vault.record_template_issuance(
            template_id=template.id,
            actor="ops",
            credential_id=uuid4(),
            context=CredentialAccessContext(workflow_id=uuid4()),
        )


def test_inmemory_remove_template_missing() -> None:
    vault = InMemoryCredentialVault()
    with pytest.raises(CredentialTemplateNotFoundError):
        vault._remove_template(uuid4())


def test_file_vault_manages_templates_and_alerts(tmp_path) -> None:
    cipher = AesGcmCredentialCipher(key="file-template")
    vault_path = tmp_path / "vault.sqlite"
    vault = FileCredentialVault(vault_path, cipher=cipher)
    template = vault.create_template(
        name="GitHub",
        provider="github",
        scopes=["repo"],
        actor="alice",
        kind="secret",
    )
    # Persist template and ensure iteration works
    reloaded = FileCredentialVault(vault_path, cipher=cipher)
    listed = reloaded.list_templates()
    assert [item.id for item in listed] == [template.id]
    fetched = reloaded.get_template(template_id=template.id)
    assert fetched.name == "GitHub"

    credential = reloaded.create_credential(
        name="GitHub", provider="github", scopes=["repo"], secret="tok", actor="ops"
    )
    alert = reloaded.record_alert(
        kind=GovernanceAlertKind.TOKEN_EXPIRING,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="expiring",
        actor="ops",
        credential_id=credential.id,
    )

    alerts = reloaded.list_alerts(include_acknowledged=True)
    assert [item.id for item in alerts] == [alert.id]
    acknowledged = reloaded.acknowledge_alert(alert.id, actor="ops")
    assert acknowledged.is_acknowledged

    with pytest.raises(GovernanceAlertNotFoundError):
        reloaded.acknowledge_alert(uuid4(), actor="ops")

    with pytest.raises(CredentialTemplateNotFoundError):
        reloaded.get_template(template_id=uuid4())

    reloaded.delete_template(template.id)
    with pytest.raises(CredentialTemplateNotFoundError):
        reloaded.get_template(template_id=template.id)


def test_file_vault_remove_template_missing(tmp_path) -> None:
    vault = FileCredentialVault(tmp_path / "vault.sqlite")
    with pytest.raises(CredentialTemplateNotFoundError):
        vault.delete_template(uuid4())


def test_file_vault_remove_template_direct(tmp_path) -> None:
    vault = FileCredentialVault(tmp_path / "vault.sqlite")
    with pytest.raises(CredentialTemplateNotFoundError):
        vault._remove_template(uuid4())


def test_file_vault_remove_alert_clears(tmp_path) -> None:
    cipher = AesGcmCredentialCipher(key="file-alert")
    vault = FileCredentialVault(tmp_path / "vault.sqlite", cipher=cipher)
    metadata = vault.create_credential(
        name="Service",
        provider="service",
        scopes=["read"],
        secret="secret",
        actor="ops",
    )
    alert = vault.record_alert(
        kind=GovernanceAlertKind.VALIDATION_FAILED,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="bad",
        actor="ops",
        credential_id=metadata.id,
    )

    vault._remove_alert(alert.id)

    assert vault.list_alerts() == []
