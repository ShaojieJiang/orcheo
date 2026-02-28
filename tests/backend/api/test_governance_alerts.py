from __future__ import annotations
from uuid import UUID, uuid4
from fastapi.testclient import TestClient
from orcheo.models import (
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialKind,
    CredentialScope,
    GovernanceAlertKind,
    SecretGovernanceAlertSeverity,
)
from orcheo.vault import InMemoryCredentialVault
from orcheo.vault.oauth import OAuthCredentialService, OAuthTokenSecrets
from .shared import StaticProvider, create_workflow_with_version


def _create_workflow(api_client: TestClient) -> UUID:
    response = api_client.post(
        "/api/workflows",
        json={"name": "Governance Flow", "actor": "tester"},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def test_acknowledge_alert_not_found_returns_404(api_client: TestClient) -> None:
    response = api_client.post(
        f"/api/credentials/governance-alerts/{uuid4()}/acknowledge",
        json={"actor": "tester"},
    )

    assert response.status_code == 404


def test_acknowledge_alert_scope_violation_returns_403(
    api_client: TestClient,
) -> None:
    workflow_id = _create_workflow(api_client)
    other_workflow_id = _create_workflow(api_client)
    vault: InMemoryCredentialVault = api_client.app.state.vault
    template = vault.create_template(
        name="Restricted",
        provider="internal",
        scopes=["read"],
        actor="tester",
        scope=CredentialScope.for_workflows(workflow_id),
    )
    alert = vault.record_alert(
        kind=GovernanceAlertKind.TOKEN_EXPIRING,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="soon",
        actor="tester",
        template_id=template.id,
        context=CredentialAccessContext(workflow_id=workflow_id),
    )

    response = api_client.post(
        f"/api/credentials/governance-alerts/{alert.id}/acknowledge",
        params={"workflow_id": str(other_workflow_id)},
        json={"actor": "tester"},
    )

    assert response.status_code == 403


def test_acknowledge_alert_requires_context_for_scoped_alert(
    api_client: TestClient,
) -> None:
    workflow_id = uuid4()
    vault: InMemoryCredentialVault = api_client.app.state.vault
    template = vault.create_template(
        name="Scoped",
        provider="internal",
        scopes=["read"],
        actor="tester",
        scope=CredentialScope.for_workflows(workflow_id),
    )
    alert = vault.record_alert(
        kind=GovernanceAlertKind.ROTATION_OVERDUE,
        severity=SecretGovernanceAlertSeverity.WARNING,
        message="rotate",
        actor="tester",
        template_id=template.id,
        context=CredentialAccessContext(workflow_id=workflow_id),
    )

    response = api_client.post(
        f"/api/credentials/governance-alerts/{alert.id}/acknowledge",
        json={"actor": "tester"},
    )

    assert response.status_code == 403


def test_governance_alert_listing_and_ack(api_client: TestClient) -> None:
    workflow_id, _ = create_workflow_with_version(api_client)
    workflow_uuid = UUID(workflow_id)
    vault: InMemoryCredentialVault = api_client.app.state.vault
    service: OAuthCredentialService = api_client.app.state.credential_service
    service.register_provider(
        "slack",
        StaticProvider(
            status=CredentialHealthStatus.UNHEALTHY,
            failure_reason="expired",
        ),
    )
    vault.create_credential(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        secret="client-secret",
        actor="tester",
        scope=CredentialScope.for_workflows(workflow_uuid),
        kind=CredentialKind.OAUTH,
        oauth_tokens=OAuthTokenSecrets(access_token="initial"),
    )

    await_response = api_client.post(
        f"/api/workflows/{workflow_id}/credentials/validate",
        json={"actor": "tester"},
    )
    assert await_response.status_code == 422

    alerts_response = api_client.get(
        "/api/credentials/governance-alerts",
        params={"workflow_id": workflow_id},
    )
    assert alerts_response.status_code == 200
    alerts = alerts_response.json()
    assert alerts and alerts[0]["kind"] == GovernanceAlertKind.VALIDATION_FAILED.value
    alert_id = alerts[0]["id"]

    ack_response = api_client.post(
        f"/api/credentials/governance-alerts/{alert_id}/acknowledge",
        params={"workflow_id": workflow_id},
        json={"actor": "tester"},
    )
    assert ack_response.status_code == 200
    assert ack_response.json()["is_acknowledged"] is True

    all_alerts = api_client.get(
        "/api/credentials/governance-alerts",
        params={
            "workflow_id": workflow_id,
            "include_acknowledged": True,
        },
    )
    assert all_alerts.status_code == 200
    assert all_alerts.json()[0]["is_acknowledged"] is True
