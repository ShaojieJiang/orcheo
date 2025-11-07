"""Alert acknowledgement and resolution tests for InMemoryCredentialVault."""

from __future__ import annotations
from uuid import uuid4
import pytest
from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialScope,
    GovernanceAlertKind,
    SecretGovernanceAlertSeverity,
)
from orcheo.vault import (
    GovernanceAlertNotFoundError,
    InMemoryCredentialVault,
    WorkflowScopeError,
)


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


def test_delete_credential_with_mixed_alerts() -> None:
    cipher = AesGcmCredentialCipher(key="delete-mixed")
    vault = InMemoryCredentialVault(cipher=cipher)

    credential_one = vault.create_credential(
        name="Service1",
        provider="service",
        scopes=["read"],
        secret="secret1",
        actor="ops",
    )

    credential_two = vault.create_credential(
        name="Service2",
        provider="service",
        scopes=["read"],
        secret="secret2",
        actor="ops",
    )

    alert_one = vault.record_alert(
        kind=GovernanceAlertKind.TOKEN_EXPIRING,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="expiring1",
        actor="ops",
        credential_id=credential_one.id,
    )

    alert_two = vault.record_alert(
        kind=GovernanceAlertKind.VALIDATION_FAILED,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="failed2",
        actor="ops",
        credential_id=credential_two.id,
    )

    global_alert = vault.record_alert(
        kind=GovernanceAlertKind.ROTATION_OVERDUE,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="global",
        actor="ops",
    )

    assert len(vault.list_alerts()) == 3

    vault.delete_credential(credential_one.id)

    remaining_alerts = vault.list_alerts()
    assert len(remaining_alerts) == 2
    assert {alert.id for alert in remaining_alerts} == {alert_two.id, global_alert.id}

    with pytest.raises(GovernanceAlertNotFoundError):
        vault.acknowledge_alert(alert_one.id, actor="ops")
