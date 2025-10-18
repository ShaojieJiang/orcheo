from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialHealthStatus,
    OAuthTokenSecrets,
)
from orcheo.vault import InMemoryCredentialVault
from orcheo.vault.templates import (
    GovernanceAlertKind,
    GovernanceAlertLevel,
    TemplateField,
    build_default_registry,
)


def test_template_registry_issues_credentials() -> None:
    cipher = AesGcmCredentialCipher(key="template-key")
    vault = InMemoryCredentialVault(cipher=cipher)
    registry = build_default_registry()

    metadata = registry.issue_from_template(
        "openai",
        vault=vault,
        actor="alice",
        workflow_id=None,
        payload={"secret": "sk-123", "organization": "org-1"},
    )

    assert metadata.provider == "openai"
    assert metadata.scope.is_unrestricted()
    assert metadata.health.status is CredentialHealthStatus.UNKNOWN


def test_template_field_validation_enforces_rules() -> None:
    field = TemplateField(
        key="secret",
        label="Secret",
        description="Must start with abc",
        validator=lambda value: None
        if value.startswith("abc")
        else (_ for _ in ()).throw(ValueError("bad")),
    )

    assert field.validate("abcdef") == "abcdef"
    with pytest.raises(ValueError):
        field.validate("xyz")


def test_governance_alerts_surface_expiring_tokens() -> None:
    cipher = AesGcmCredentialCipher(key="governance")
    vault = InMemoryCredentialVault(cipher=cipher)
    registry = build_default_registry()
    workflow_id = uuid4()
    context = CredentialAccessContext(workflow_id=workflow_id)

    metadata = registry.issue_from_template(
        "slack",
        vault=vault,
        actor="alice",
        workflow_id=workflow_id,
        payload={
            "secret": "xoxb-token",
            "signing_secret": "secret",
        },
        oauth_tokens=OAuthTokenSecrets(
            access_token="token",
            refresh_token="refresh",
            expires_at=datetime.now(tz=UTC) + timedelta(days=1),
        ),
    )

    vault.mark_health(
        credential_id=metadata.id,
        status=CredentialHealthStatus.UNHEALTHY,
        reason="oauth failure",
        actor="auditor",
        context=context,
    )

    alerts = registry.evaluate_workflow_governance(
        vault=vault,
        workflow_id=workflow_id,
        context=context,
    )

    kinds = {alert.kind for alert in alerts}
    assert GovernanceAlertKind.EXPIRING in kinds
    assert GovernanceAlertKind.HEALTH_UNHEALTHY in kinds
    levels = {alert.level for alert in alerts}
    assert GovernanceAlertLevel.CRITICAL in levels
