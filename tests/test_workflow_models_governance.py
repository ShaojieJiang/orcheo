"""Secret governance alert tests split from the original suite."""

from __future__ import annotations
from uuid import uuid4
from orcheo.models import (
    CredentialScope,
    GovernanceAlertKind,
    SecretGovernanceAlert,
    SecretGovernanceAlertSeverity,
)


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
