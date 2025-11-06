from __future__ import annotations
from datetime import UTC, datetime, timedelta
from uuid import UUID
from fastapi.testclient import TestClient
from orcheo.models import CredentialHealthStatus, CredentialKind, CredentialScope
from orcheo.vault.oauth import OAuthCredentialService, OAuthTokenSecrets
from .shared import StaticProvider, create_workflow_with_version


def test_credential_validation_endpoint_blocks_unhealthy_run(
    api_client: TestClient,
) -> None:
    workflow_id, version_id = create_workflow_with_version(api_client)
    workflow_uuid = UUID(workflow_id)
    vault = api_client.app.state.vault
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

    run_response = api_client.post(
        f"/api/workflows/{workflow_id}/runs",
        json={
            "workflow_version_id": version_id,
            "triggered_by": "tester",
            "input_payload": {},
        },
    )
    assert run_response.status_code == 422
    detail = run_response.json()
    if "detail" in detail and isinstance(detail["detail"], dict):
        assert "failures" in detail["detail"]
    else:
        assert "failures" in detail


def test_credential_endpoints_report_health(api_client: TestClient) -> None:
    workflow_id, _ = create_workflow_with_version(api_client)
    workflow_uuid = UUID(workflow_id)
    vault = api_client.app.state.vault
    service: OAuthCredentialService = api_client.app.state.credential_service
    service.register_provider("feedly", StaticProvider())
    vault.create_credential(
        name="Feedly",
        provider="feedly",
        scopes=["read"],
        secret="client-secret",
        actor="tester",
        scope=CredentialScope.for_workflows(workflow_uuid),
        kind=CredentialKind.OAUTH,
        oauth_tokens=OAuthTokenSecrets(
            access_token="initial",
            expires_at=datetime.now(tz=UTC) + timedelta(minutes=10),
        ),
    )

    validate_response = api_client.post(
        f"/api/workflows/{workflow_id}/credentials/validate",
        json={"actor": "tester"},
    )
    assert validate_response.status_code == 200
    payload = validate_response.json()
    assert payload["status"] == CredentialHealthStatus.HEALTHY.value

    health_response = api_client.get(f"/api/workflows/{workflow_id}/credentials/health")
    assert health_response.status_code == 200
    health_payload = health_response.json()
    assert health_payload["status"] == CredentialHealthStatus.HEALTHY.value
    assert health_payload["credentials"]
