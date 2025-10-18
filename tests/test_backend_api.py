"""End-to-end API tests for the Orcheo FastAPI backend."""

from __future__ import annotations
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
import importlib
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialKind,
    CredentialScope,
    GovernanceAlertKind,
    SecretGovernanceAlertSeverity,
    OAuthTokenSecrets,
)
from orcheo.vault import (
    CredentialTemplateNotFoundError,
    InMemoryCredentialVault,
    WorkflowScopeError,
)
from orcheo.vault.oauth import (
    OAuthCredentialService,
    OAuthProvider,
    OAuthValidationResult,
)

backend_app = importlib.import_module("orcheo_backend.app")
from orcheo_backend.app import create_app
from orcheo_backend.app.repository import InMemoryWorkflowRepository
from orcheo_backend.app.schemas import (
    CredentialIssuancePolicyPayload,
    CredentialScopePayload,
    OAuthTokenRequest,
)


class StaticProvider(OAuthProvider):
    """Simple provider that returns predetermined validation results."""

    def __init__(
        self,
        *,
        status: CredentialHealthStatus = CredentialHealthStatus.HEALTHY,
        failure_reason: str | None = None,
    ) -> None:
        self.status = status
        self.failure_reason = failure_reason
        self.refresh_calls = 0

    async def refresh_tokens(self, metadata, tokens):  # type: ignore[override]
        self.refresh_calls += 1
        return OAuthTokenSecrets(
            access_token="refreshed-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

    async def validate_tokens(self, metadata, tokens):  # type: ignore[override]
        return OAuthValidationResult(
            status=self.status, failure_reason=self.failure_reason
        )


@pytest.fixture()
def api_client() -> Iterator[TestClient]:
    """Yield a configured API client backed by a fresh repository."""

    cipher = AesGcmCredentialCipher(key="api-client-key")
    vault = InMemoryCredentialVault(cipher=cipher)
    service = OAuthCredentialService(vault, token_ttl_seconds=600, providers={})
    repository = InMemoryWorkflowRepository(credential_service=service)
    app = create_app(repository, credential_service=service)
    app.state.vault = vault
    app.state.credential_service = service
    with TestClient(app) as client:
        yield client


def test_backend_helper_builders_and_scope_errors() -> None:
    scope_payload = CredentialScopePayload(
        workflow_ids=[uuid4()],
        workspace_ids=[uuid4()],
        roles=["admin"],
    )
    scope = backend_app._build_scope(scope_payload)
    assert scope.workflow_ids

    assert backend_app._build_scope(None) is None

    policy_payload = CredentialIssuancePolicyPayload(
        require_refresh_token=True,
        rotation_period_days=7,
        expiry_threshold_minutes=30,
    )
    policy = backend_app._build_policy(policy_payload)
    assert policy.require_refresh_token is True

    token_payload = OAuthTokenRequest(
        access_token="a", refresh_token="b", expires_at=datetime.now(tz=UTC)
    )
    tokens = backend_app._build_oauth_tokens(token_payload)
    assert tokens.refresh_token == "b"
    assert backend_app._build_oauth_tokens(None) is None

    workflow_id = uuid4()
    context = backend_app._context_from_workflow(workflow_id)
    assert context is not None and context.workflow_id == workflow_id
    assert backend_app._context_from_workflow(None) is None

    with pytest.raises(HTTPException) as excinfo:
        backend_app._raise_scope_error(WorkflowScopeError("denied"))
    assert excinfo.value.status_code == 403


def test_get_vault_initializes_when_missing(monkeypatch) -> None:
    created: dict[str, bool] = {}

    def fake_create(settings: Any) -> InMemoryCredentialVault:
        created["called"] = True
        return InMemoryCredentialVault()

    monkeypatch.setitem(backend_app._vault_ref, "vault", None)
    monkeypatch.setitem(backend_app._credential_service_ref, "service", None)
    monkeypatch.setattr(backend_app, "_create_vault", fake_create)
    monkeypatch.setattr(backend_app, "get_settings", lambda: object())

    vault = backend_app.get_vault()

    assert created == {"called": True}
    assert isinstance(vault, InMemoryCredentialVault)


def _create_workflow_with_version(api_client: TestClient) -> tuple[str, str]:
    """Create a workflow and a single version, returning their identifiers."""

    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Webhook Flow", "actor": "tester"},
    )
    workflow_response.raise_for_status()
    workflow_id = workflow_response.json()["id"]

    version_response = api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {"nodes": ["start"], "edges": []},
            "metadata": {},
            "created_by": "tester",
        },
    )
    version_response.raise_for_status()
    version_id = version_response.json()["id"]

    return workflow_id, version_id


def test_credential_validation_endpoint_blocks_unhealthy_run(
    api_client: TestClient,
) -> None:
    workflow_id, version_id = _create_workflow_with_version(api_client)
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
    workflow_id, _ = _create_workflow_with_version(api_client)
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


def test_credential_template_crud_and_issuance(api_client: TestClient) -> None:
    create_response = api_client.post(
        "/api/credentials/templates",
        json={
            "name": "GitHub",
            "provider": "github",
            "scopes": ["repo:read"],
            "description": "GitHub token",
            "kind": "secret",
            "actor": "tester",
        },
    )
    assert create_response.status_code == 201
    template = create_response.json()
    template_id = template["id"]

    fetch_response = api_client.get(f"/api/credentials/templates/{template_id}")
    assert fetch_response.status_code == 200

    list_response = api_client.get("/api/credentials/templates")
    assert list_response.status_code == 200
    assert any(item["id"] == template_id for item in list_response.json())

    update_response = api_client.patch(
        f"/api/credentials/templates/{template_id}",
        json={"description": "Rotated", "actor": "tester"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["description"] == "Rotated"

    issue_response = api_client.post(
        f"/api/credentials/templates/{template_id}/issue",
        json={
            "template_id": template_id,
            "secret": "sup3r-secret",
            "actor": "tester",
            "name": "GitHub Prod",
        },
    )
    assert issue_response.status_code == 201
    issued = issue_response.json()
    assert issued["name"] == "GitHub Prod"
    assert issued["template_id"] == template_id

    vault: InMemoryCredentialVault = api_client.app.state.vault
    stored = vault.list_credentials()
    assert any(item.template_id == UUID(template_id) for item in stored)

    delete_response = api_client.delete(f"/api/credentials/templates/{template_id}")
    assert delete_response.status_code == 204

    get_response = api_client.get(f"/api/credentials/templates/{template_id}")
    assert get_response.status_code == 404


def test_credential_template_get_scope_violation_returns_403(
    api_client: TestClient,
) -> None:
    workflow_id = uuid4()
    create_response = api_client.post(
        "/api/credentials/templates",
        json={
            "name": "Restricted",
            "provider": "internal",
            "scopes": ["read"],
            "scope": {"workflow_ids": [str(workflow_id)]},
            "actor": "tester",
        },
    )
    template_id = create_response.json()["id"]

    response = api_client.get(
        f"/api/credentials/templates/{template_id}",
        params={"workflow_id": str(uuid4())},
    )

    assert response.status_code == 403


def test_credential_template_update_not_found_returns_404(
    api_client: TestClient,
) -> None:
    response = api_client.patch(
        f"/api/credentials/templates/{uuid4()}",
        json={"actor": "tester"},
    )

    assert response.status_code == 404


def test_credential_template_update_scope_violation_returns_403(
    api_client: TestClient,
) -> None:
    workflow_id = uuid4()
    create_response = api_client.post(
        "/api/credentials/templates",
        json={
            "name": "Restricted",
            "provider": "internal",
            "scopes": ["read"],
            "scope": {"workflow_ids": [str(workflow_id)]},
            "actor": "tester",
        },
    )
    template_id = create_response.json()["id"]

    response = api_client.patch(
        f"/api/credentials/templates/{template_id}",
        params={"workflow_id": str(uuid4())},
        json={"description": "updated", "actor": "tester"},
    )

    assert response.status_code == 403


def test_credential_template_delete_not_found_returns_404(
    api_client: TestClient,
) -> None:
    response = api_client.delete(f"/api/credentials/templates/{uuid4()}")

    assert response.status_code == 404


def test_credential_template_delete_scope_violation_returns_403(
    api_client: TestClient,
) -> None:
    workflow_id = uuid4()
    create_response = api_client.post(
        "/api/credentials/templates",
        json={
            "name": "Restricted",
            "provider": "internal",
            "scopes": ["read"],
            "scope": {"workflow_ids": [str(workflow_id)]},
            "actor": "tester",
        },
    )
    template_id = create_response.json()["id"]

    response = api_client.delete(
        f"/api/credentials/templates/{template_id}",
        params={"workflow_id": str(uuid4())},
    )

    assert response.status_code == 403


def test_issue_template_without_service_returns_503(api_client: TestClient) -> None:
    create_response = api_client.post(
        "/api/credentials/templates",
        json={
            "name": "GitHub",
            "provider": "github",
            "scopes": ["repo"],
            "actor": "tester",
        },
    )
    template_id = create_response.json()["id"]

    api_client.app.dependency_overrides[backend_app.get_vault] = (
        lambda: api_client.app.state.vault
    )
    api_client.app.dependency_overrides[backend_app.get_credential_service] = (
        lambda: None
    )

    response = api_client.post(
        f"/api/credentials/templates/{template_id}/issue",
        json={"template_id": template_id, "secret": "s", "actor": "tester"},
    )

    api_client.app.dependency_overrides.clear()
    assert response.status_code == 503


def test_issue_template_value_error_returns_400(api_client: TestClient) -> None:
    create_response = api_client.post(
        "/api/credentials/templates",
        json={
            "name": "GitHub",
            "provider": "github",
            "scopes": ["repo"],
            "actor": "tester",
        },
    )
    template_id = create_response.json()["id"]

    class RaisingService:
        def issue_from_template(self, **_: Any):
            raise ValueError("invalid")

    api_client.app.dependency_overrides[backend_app.get_vault] = (
        lambda: api_client.app.state.vault
    )
    api_client.app.dependency_overrides[backend_app.get_credential_service] = (
        lambda: RaisingService()
    )

    response = api_client.post(
        f"/api/credentials/templates/{template_id}/issue",
        json={"template_id": template_id, "secret": "s", "actor": "tester"},
    )

    api_client.app.dependency_overrides.clear()
    assert response.status_code == 400


def test_issue_template_not_found_returns_404(api_client: TestClient) -> None:
    class MissingTemplateService:
        def issue_from_template(self, **_: Any):
            raise CredentialTemplateNotFoundError("missing")

    api_client.app.dependency_overrides[backend_app.get_vault] = (
        lambda: api_client.app.state.vault
    )
    api_client.app.dependency_overrides[backend_app.get_credential_service] = (
        lambda: MissingTemplateService()
    )

    response = api_client.post(
        f"/api/credentials/templates/{uuid4()}/issue",
        json={"template_id": str(uuid4()), "secret": "s", "actor": "tester"},
    )

    api_client.app.dependency_overrides.clear()
    assert response.status_code == 404


def test_issue_template_scope_violation_returns_403(api_client: TestClient) -> None:
    workflow_id = uuid4()
    create_response = api_client.post(
        "/api/credentials/templates",
        json={
            "name": "Restricted",
            "provider": "internal",
            "scopes": ["read"],
            "scope": {"workflow_ids": [str(workflow_id)]},
            "actor": "tester",
        },
    )
    template_id = create_response.json()["id"]

    class ScopeDeniedService:
        def issue_from_template(self, **_: Any):
            raise WorkflowScopeError("denied")

    api_client.app.dependency_overrides[backend_app.get_vault] = (
        lambda: api_client.app.state.vault
    )
    api_client.app.dependency_overrides[backend_app.get_credential_service] = (
        lambda: ScopeDeniedService()
    )

    response = api_client.post(
        f"/api/credentials/templates/{template_id}/issue",
        json={
            "template_id": template_id,
            "secret": "s",
            "actor": "tester",
            "workflow_id": str(uuid4()),
        },
    )

    api_client.app.dependency_overrides.clear()
    assert response.status_code == 403


def test_acknowledge_alert_not_found_returns_404(api_client: TestClient) -> None:
    response = api_client.post(
        f"/api/credentials/governance-alerts/{uuid4()}/acknowledge",
        json={"actor": "tester"},
    )

    assert response.status_code == 404


def test_acknowledge_alert_scope_violation_returns_403(
    api_client: TestClient,
) -> None:
    workflow_id = uuid4()
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
        params={"workflow_id": str(uuid4())},
        json={"actor": "tester"},
    )

    assert response.status_code == 403


def test_governance_alert_listing_and_ack(api_client: TestClient) -> None:
    workflow_id, _ = _create_workflow_with_version(api_client)
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

    alerts_response = api_client.get("/api/credentials/governance-alerts")
    assert alerts_response.status_code == 200
    alerts = alerts_response.json()
    assert alerts and alerts[0]["kind"] == GovernanceAlertKind.VALIDATION_FAILED.value
    alert_id = alerts[0]["id"]

    ack_response = api_client.post(
        f"/api/credentials/governance-alerts/{alert_id}/acknowledge",
        json={"actor": "tester"},
    )
    assert ack_response.status_code == 200
    assert ack_response.json()["is_acknowledged"] is True

    all_alerts = api_client.get(
        "/api/credentials/governance-alerts",
        params={"include_acknowledged": True},
    )
    assert all_alerts.status_code == 200
    assert all_alerts.json()[0]["is_acknowledged"] is True


def test_workflow_crud_operations(api_client: TestClient) -> None:
    """Validate workflow creation, retrieval, update, and archival."""

    create_response = api_client.post(
        "/api/workflows",
        json={
            "name": "Sample Flow",
            "description": "Initial description",
            "tags": ["Demo", "Example"],
            "actor": "tester",
        },
    )
    assert create_response.status_code == 201
    workflow = create_response.json()
    workflow_id = workflow["id"]
    assert workflow["slug"] == "sample-flow"

    get_response = api_client.get(f"/api/workflows/{workflow_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Sample Flow"

    update_response = api_client.put(
        f"/api/workflows/{workflow_id}",
        json={"description": "Updated description", "actor": "tester"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["description"] == "Updated description"

    list_response = api_client.get("/api/workflows")
    assert list_response.status_code == 200
    assert any(item["id"] == workflow_id for item in list_response.json())

    delete_response = api_client.delete(
        f"/api/workflows/{workflow_id}",
        params={"actor": "tester"},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["is_archived"] is True


def test_workflow_versions_and_diff(api_client: TestClient) -> None:
    """Ensure version creation, retrieval, and diffing all function."""

    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Diff Flow", "actor": "author"},
    )
    workflow = workflow_response.json()
    workflow_id = workflow["id"]

    version_one = api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {"nodes": ["start"], "edges": []},
            "metadata": {"notes": "v1"},
            "created_by": "author",
        },
    )
    assert version_one.status_code == 201
    version_two = api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {
                "nodes": ["start", "end"],
                "edges": [{"from": "start", "to": "end"}],
            },
            "metadata": {"notes": "v2"},
            "created_by": "author",
            "notes": "Adds end node",
        },
    )
    assert version_two.status_code == 201

    list_versions = api_client.get(f"/api/workflows/{workflow_id}/versions")
    assert list_versions.status_code == 200
    versions = list_versions.json()
    assert [version["version"] for version in versions] == [1, 2]

    version_detail = api_client.get(f"/api/workflows/{workflow_id}/versions/2")
    assert version_detail.status_code == 200
    assert version_detail.json()["version"] == 2

    diff_response = api_client.get(f"/api/workflows/{workflow_id}/versions/1/diff/2")
    assert diff_response.status_code == 200
    diff_payload = diff_response.json()
    assert diff_payload["base_version"] == 1
    assert diff_payload["target_version"] == 2
    diff_lines = diff_payload["diff"]
    assert any('+    "end"' in line for line in diff_lines)


def test_workflow_run_lifecycle(api_client: TestClient) -> None:
    """Exercise the workflow run state transitions."""

    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Run Flow", "actor": "runner"},
    )
    workflow_id = workflow_response.json()["id"]

    version_response = api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {"nodes": ["start"], "edges": []},
            "metadata": {},
            "created_by": "runner",
        },
    )
    version_id = UUID(version_response.json()["id"])

    run_response = api_client.post(
        f"/api/workflows/{workflow_id}/runs",
        json={
            "workflow_version_id": str(version_id),
            "triggered_by": "runner",
            "input_payload": {"input": "value"},
        },
    )
    assert run_response.status_code == 201
    run_payload = run_response.json()
    run_id = run_payload["id"]
    assert run_payload["status"] == "pending"

    start_response = api_client.post(
        f"/api/runs/{run_id}/start",
        json={"actor": "runner"},
    )
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"

    succeed_response = api_client.post(
        f"/api/runs/{run_id}/succeed",
        json={"actor": "runner", "output": {"result": "ok"}},
    )
    assert succeed_response.status_code == 200
    succeeded_payload = succeed_response.json()
    assert succeeded_payload["status"] == "succeeded"
    assert succeeded_payload["output_payload"]["result"] == "ok"

    list_runs_response = api_client.get(f"/api/workflows/{workflow_id}/runs")
    assert list_runs_response.status_code == 200
    run_ids = [run["id"] for run in list_runs_response.json()]
    assert run_id in run_ids

    run_detail = api_client.get(f"/api/runs/{run_id}")
    assert run_detail.status_code == 200
    assert run_detail.json()["status"] == "succeeded"


def test_workflow_run_invalid_transitions(api_client: TestClient) -> None:
    """Invalid run transitions return conflict responses with helpful details."""

    workflow = api_client.post(
        "/api/workflows",
        json={"name": "Conflict Flow", "actor": "runner"},
    ).json()
    workflow_id = workflow["id"]

    version = api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={"graph": {}, "metadata": {}, "created_by": "runner"},
    ).json()

    run = api_client.post(
        f"/api/workflows/{workflow_id}/runs",
        json={
            "workflow_version_id": version["id"],
            "triggered_by": "runner",
            "input_payload": {},
        },
    ).json()
    run_id = run["id"]

    succeed_before_start = api_client.post(
        f"/api/runs/{run_id}/succeed",
        json={"actor": "runner", "output": {}},
    )
    assert succeed_before_start.status_code == 409
    assert (
        succeed_before_start.json()["detail"]
        == "Only running runs can be marked as succeeded."
    )

    start_response = api_client.post(
        f"/api/runs/{run_id}/start",
        json={"actor": "runner"},
    )
    assert start_response.status_code == 200

    restart_response = api_client.post(
        f"/api/runs/{run_id}/start",
        json={"actor": "runner"},
    )
    assert restart_response.status_code == 409
    assert restart_response.json()["detail"] == "Only pending runs can be started."

    succeed_response = api_client.post(
        f"/api/runs/{run_id}/succeed",
        json={"actor": "runner", "output": {"result": "ok"}},
    )
    assert succeed_response.status_code == 200

    fail_after_completion = api_client.post(
        f"/api/runs/{run_id}/fail",
        json={"actor": "runner", "error": "boom"},
    )
    assert fail_after_completion.status_code == 409
    assert (
        fail_after_completion.json()["detail"]
        == "Only pending or running runs can be marked as failed."
    )

    cancel_after_completion = api_client.post(
        f"/api/runs/{run_id}/cancel",
        json={"actor": "runner", "reason": None},
    )
    assert cancel_after_completion.status_code == 409
    assert (
        cancel_after_completion.json()["detail"]
        == "Cannot cancel a run that is already completed."
    )


def test_not_found_responses(api_client: TestClient) -> None:
    """The API surfaces standardized 404 errors when entities are missing."""

    missing_id = "00000000-0000-0000-0000-000000000000"

    workflow_response = api_client.get(f"/api/workflows/{missing_id}")
    assert workflow_response.status_code == 404
    assert workflow_response.json()["detail"] == "Workflow not found"

    run_response = api_client.get(f"/api/runs/{missing_id}")
    assert run_response.status_code == 404
    assert run_response.json()["detail"] == "Workflow run not found"


def test_version_and_run_error_responses(api_client: TestClient) -> None:
    """Version and run routes propagate repository errors as 404 responses."""

    missing = str(uuid4())

    update_response = api_client.put(
        f"/api/workflows/{missing}", json={"actor": "tester"}
    )
    assert update_response.status_code == 404

    delete_response = api_client.delete(
        f"/api/workflows/{missing}", params={"actor": "tester"}
    )
    assert delete_response.status_code == 404

    create_version_missing = api_client.post(
        f"/api/workflows/{missing}/versions",
        json={
            "graph": {},
            "metadata": {},
            "created_by": "tester",
        },
    )
    assert create_version_missing.status_code == 404

    list_versions_missing = api_client.get(f"/api/workflows/{missing}/versions")
    assert list_versions_missing.status_code == 404

    missing_version_for_missing_workflow = api_client.get(
        f"/api/workflows/{missing}/versions/1"
    )
    assert missing_version_for_missing_workflow.status_code == 404

    workflow = api_client.post(
        "/api/workflows",
        json={"name": "Error Flow", "actor": "tester"},
    ).json()
    workflow_id = workflow["id"]

    api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={"graph": {}, "metadata": {}, "created_by": "tester"},
    )

    missing_version_response = api_client.get(
        f"/api/workflows/{workflow_id}/versions/99"
    )
    assert missing_version_response.status_code == 404
    assert missing_version_response.json()["detail"] == "Workflow version not found"

    diff_missing_version = api_client.get(
        f"/api/workflows/{workflow_id}/versions/1/diff/99"
    )
    assert diff_missing_version.status_code == 404

    diff_missing_workflow = api_client.get(
        f"/api/workflows/{missing}/versions/1/diff/1"
    )
    assert diff_missing_workflow.status_code == 404
    assert diff_missing_workflow.json()["detail"] == "Workflow not found"

    create_run_missing_version = api_client.post(
        f"/api/workflows/{workflow_id}/runs",
        json={
            "workflow_version_id": str(uuid4()),
            "triggered_by": "tester",
            "input_payload": {},
        },
    )
    assert create_run_missing_version.status_code == 404
    assert create_run_missing_version.json()["detail"] == "Workflow version not found"

    create_run_missing_workflow = api_client.post(
        f"/api/workflows/{missing}/runs",
        json={
            "workflow_version_id": str(uuid4()),
            "triggered_by": "tester",
            "input_payload": {},
        },
    )
    assert create_run_missing_workflow.status_code == 404
    assert create_run_missing_workflow.json()["detail"] == "Workflow not found"

    list_runs_missing = api_client.get(f"/api/workflows/{missing}/runs")
    assert list_runs_missing.status_code == 404

    for endpoint in [
        "start",
        "succeed",
        "fail",
        "cancel",
    ]:
        payload: dict[str, object] = {"actor": "tester"}
        if endpoint == "succeed":
            payload["output"] = None
        if endpoint == "fail":
            payload["error"] = "boom"
        if endpoint == "cancel":
            payload["reason"] = None
        response = api_client.post(
            f"/api/runs/{missing}/{endpoint}",
            json=payload,
        )
        assert response.status_code == 404


def test_webhook_trigger_configuration_roundtrip(api_client: TestClient) -> None:
    """Validate webhook trigger configuration persistence."""

    workflow_id, _ = _create_workflow_with_version(api_client)

    default_response = api_client.get(
        f"/api/workflows/{workflow_id}/triggers/webhook/config"
    )
    assert default_response.status_code == 200
    default_payload = default_response.json()
    assert set(default_payload["allowed_methods"]) == {"POST"}

    update_response = api_client.put(
        f"/api/workflows/{workflow_id}/triggers/webhook/config",
        json={
            "allowed_methods": ["POST", "GET"],
            "required_headers": {"x-custom": "value"},
            "required_query_params": {"env": "prod"},
            "shared_secret": "super-secret",
            "secret_header": "x-super-secret",
            "rate_limit": {"limit": 5, "interval_seconds": 60},
        },
    )
    assert update_response.status_code == 200
    updated_payload = update_response.json()
    assert set(updated_payload["allowed_methods"]) == {"POST", "GET"}
    assert updated_payload["required_headers"] == {"x-custom": "value"}
    assert updated_payload["required_query_params"] == {"env": "prod"}
    assert updated_payload["shared_secret"] == "super-secret"
    assert updated_payload["secret_header"] == "x-super-secret"

    roundtrip_response = api_client.get(
        f"/api/workflows/{workflow_id}/triggers/webhook/config"
    )
    assert roundtrip_response.status_code == 200
    assert roundtrip_response.json() == updated_payload


def test_webhook_trigger_execution_creates_run(api_client: TestClient) -> None:
    """Ensure webhook invocation creates a pending workflow run."""

    workflow_id, _ = _create_workflow_with_version(api_client)

    api_client.put(
        f"/api/workflows/{workflow_id}/triggers/webhook/config",
        json={
            "allowed_methods": ["POST"],
            "required_headers": {"x-custom": "value"},
            "shared_secret": "token",
            "secret_header": "x-auth",
            "rate_limit": {"limit": 5, "interval_seconds": 60},
        },
    )

    trigger_response = api_client.post(
        f"/api/workflows/{workflow_id}/triggers/webhook",
        json={"message": "hello"},
        headers={
            "x-custom": "value",
            "x-auth": "token",
        },
        params={"extra": "context"},
    )
    assert trigger_response.status_code == 202
    run_payload = trigger_response.json()
    assert run_payload["triggered_by"] == "webhook"
    assert run_payload["status"] == "pending"

    runs_response = api_client.get(f"/api/workflows/{workflow_id}/runs")
    assert runs_response.status_code == 200
    runs = runs_response.json()
    assert len(runs) == 1
    stored_run = runs[0]
    assert stored_run["input_payload"]["body"] == {"message": "hello"}
    assert stored_run["input_payload"]["headers"]["x-custom"] == "value"
    assert stored_run["input_payload"]["query_params"] == {"extra": "context"}


def test_webhook_trigger_enforces_method_and_rate_limit(
    api_client: TestClient,
) -> None:
    """Ensure webhook trigger enforces method filters and rate limiting."""

    workflow_id, _ = _create_workflow_with_version(api_client)

    api_client.put(
        f"/api/workflows/{workflow_id}/triggers/webhook/config",
        json={
            "allowed_methods": ["GET"],
            "rate_limit": {"limit": 1, "interval_seconds": 60},
        },
    )

    post_response = api_client.post(
        f"/api/workflows/{workflow_id}/triggers/webhook",
    )
    assert post_response.status_code == 405

    first_get = api_client.get(f"/api/workflows/{workflow_id}/triggers/webhook")
    assert first_get.status_code == 202

    second_get = api_client.get(f"/api/workflows/{workflow_id}/triggers/webhook")
    assert second_get.status_code == 429


def test_webhook_trigger_config_missing_workflow(api_client: TestClient) -> None:
    """Webhook config routes return 404 for unknown workflows."""

    missing = str(uuid4())
    response = api_client.put(
        f"/api/workflows/{missing}/triggers/webhook/config",
        json={"allowed_methods": ["POST"]},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Workflow not found"

    get_response = api_client.get(f"/api/workflows/{missing}/triggers/webhook/config")
    assert get_response.status_code == 404
    assert get_response.json()["detail"] == "Workflow not found"


def test_webhook_trigger_invoke_missing_workflow(api_client: TestClient) -> None:
    """Webhook invocation returns a not found error for unknown workflows."""

    missing = str(uuid4())
    response = api_client.post(f"/api/workflows/{missing}/triggers/webhook")
    assert response.status_code == 404
    assert response.json()["detail"] == "Workflow not found"


def test_webhook_trigger_invoke_requires_version(api_client: TestClient) -> None:
    """Webhook invocation requires at least one workflow version."""

    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "No Version Flow", "actor": "tester"},
    )
    workflow_id = workflow_response.json()["id"]

    response = api_client.post(f"/api/workflows/{workflow_id}/triggers/webhook")
    assert response.status_code == 404
    assert response.json()["detail"] == "Workflow version not found"


def test_webhook_trigger_accepts_non_json_body(api_client: TestClient) -> None:
    """Webhook invocation stores non-JSON payloads as raw bytes."""

    workflow_id, _ = _create_workflow_with_version(api_client)

    api_client.put(
        f"/api/workflows/{workflow_id}/triggers/webhook/config",
        json={"allowed_methods": ["POST"]},
    )

    binary_payload = b"\xff\xfe"
    trigger_response = api_client.post(
        f"/api/workflows/{workflow_id}/triggers/webhook",
        content=binary_payload,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert trigger_response.status_code == 202

    runs_response = api_client.get(f"/api/workflows/{workflow_id}/runs")
    run_payload = runs_response.json()[0]["input_payload"]
    assert run_payload["body"] == {"raw": "��"}


def test_cron_trigger_config_endpoints_require_known_workflow(
    api_client: TestClient,
) -> None:
    """Cron configuration endpoints return 404 for unknown workflows."""

    missing_id = uuid4()

    update_response = api_client.put(
        f"/api/workflows/{missing_id}/triggers/cron/config",
        json={
            "expression": "0 12 * * *",
            "timezone": "UTC",
            "allow_overlapping": False,
        },
    )
    assert update_response.status_code == 404
    assert update_response.json()["detail"] == "Workflow not found"

    fetch_response = api_client.get(f"/api/workflows/{missing_id}/triggers/cron/config")
    assert fetch_response.status_code == 404
    assert fetch_response.json()["detail"] == "Workflow not found"


def test_cron_trigger_configuration_roundtrip(api_client: TestClient) -> None:
    """Cron trigger configuration can be updated and retrieved."""

    workflow_id, _ = _create_workflow_with_version(api_client)

    default_response = api_client.get(
        f"/api/workflows/{workflow_id}/triggers/cron/config"
    )
    assert default_response.status_code == 200
    assert default_response.json()["expression"] == "0 * * * *"

    update_response = api_client.put(
        f"/api/workflows/{workflow_id}/triggers/cron/config",
        json={
            "expression": "0 9 * * MON-FRI",
            "timezone": "America/New_York",
            "allow_overlapping": False,
        },
    )
    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["expression"] == "0 9 * * MON-FRI"
    assert payload["timezone"] == "America/New_York"
    assert payload["allow_overlapping"] is False

    roundtrip = api_client.get(f"/api/workflows/{workflow_id}/triggers/cron/config")
    assert roundtrip.status_code == 200
    assert roundtrip.json() == payload


def test_cron_trigger_dispatch_and_overlap(api_client: TestClient) -> None:
    """Cron dispatch endpoint enqueues due runs and enforces overlap guard."""

    workflow_id, _ = _create_workflow_with_version(api_client)

    api_client.put(
        f"/api/workflows/{workflow_id}/triggers/cron/config",
        json={
            "expression": "0 9 * * *",
            "timezone": "UTC",
            "allow_overlapping": False,
        },
    )

    dispatch_response = api_client.post(
        "/api/triggers/cron/dispatch",
        json={"now": datetime(2025, 1, 1, 9, 0, tzinfo=UTC).isoformat()},
    )
    assert dispatch_response.status_code == 200
    runs = dispatch_response.json()
    assert len(runs) == 1
    run_id = runs[0]["id"]
    assert runs[0]["triggered_by"] == "cron"

    blocked = api_client.post(
        "/api/triggers/cron/dispatch",
        json={"now": datetime(2025, 1, 1, 10, 0, tzinfo=UTC).isoformat()},
    )
    assert blocked.status_code == 200
    assert blocked.json() == []

    start_response = api_client.post(
        f"/api/runs/{run_id}/start",
        json={"actor": "cron"},
    )
    assert start_response.status_code == 200

    succeed_response = api_client.post(
        f"/api/runs/{run_id}/succeed",
        json={"actor": "cron"},
    )
    assert succeed_response.status_code == 200

    next_dispatch = api_client.post(
        "/api/triggers/cron/dispatch",
        json={"now": datetime(2025, 1, 2, 9, 0, tzinfo=UTC).isoformat()},
    )
    assert next_dispatch.status_code == 200
    assert len(next_dispatch.json()) == 1


def test_cron_trigger_timezone_dispatch(api_client: TestClient) -> None:
    """Cron dispatch respects configured timezones when evaluating schedules."""

    workflow_id, _ = _create_workflow_with_version(api_client)

    api_client.put(
        f"/api/workflows/{workflow_id}/triggers/cron/config",
        json={
            "expression": "0 9 * * *",
            "timezone": "America/Los_Angeles",
        },
    )

    dispatch_response = api_client.post(
        "/api/triggers/cron/dispatch",
        json={"now": datetime(2025, 1, 1, 17, 0, tzinfo=UTC).isoformat()},
    )
    assert dispatch_response.status_code == 200
    assert len(dispatch_response.json()) == 1


def test_manual_trigger_dispatch_single_run(api_client: TestClient) -> None:
    """Manual trigger endpoint creates a run with the latest version."""

    workflow_id, _ = _create_workflow_with_version(api_client)

    dispatch_response = api_client.post(
        "/api/triggers/manual/dispatch",
        json={
            "workflow_id": workflow_id,
            "actor": "operator",
            "runs": [{"input_payload": {"foo": "bar"}}],
        },
    )
    assert dispatch_response.status_code == 200
    runs = dispatch_response.json()
    assert len(runs) == 1
    run = runs[0]
    assert run["triggered_by"] == "manual"
    assert run["input_payload"] == {"foo": "bar"}

    detail_response = api_client.get(f"/api/runs/{run['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["audit_log"][0]["actor"] == "operator"


def test_manual_trigger_dispatch_batch(api_client: TestClient) -> None:
    """Batch manual dispatch honors explicit version overrides."""

    workflow_id, version_one = _create_workflow_with_version(api_client)
    version_two_response = api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {"nodes": ["start", "branch"], "edges": []},
            "metadata": {},
            "created_by": "tester",
        },
    )
    assert version_two_response.status_code == 201
    version_two = version_two_response.json()["id"]

    dispatch_response = api_client.post(
        "/api/triggers/manual/dispatch",
        json={
            "workflow_id": workflow_id,
            "actor": "batcher",
            "runs": [
                {
                    "workflow_version_id": version_one,
                    "input_payload": {"index": 1},
                },
                {
                    "workflow_version_id": version_two,
                    "input_payload": {"index": 2},
                },
            ],
        },
    )
    assert dispatch_response.status_code == 200
    runs = dispatch_response.json()
    assert [run["triggered_by"] for run in runs] == ["manual_batch", "manual_batch"]
    assert [run["workflow_version_id"] for run in runs] == [
        version_one,
        version_two,
    ]


def test_manual_trigger_dispatch_errors(api_client: TestClient) -> None:
    """Manual dispatch returns 404 when workflow or versions are missing."""

    missing_workflow = uuid4()
    missing_response = api_client.post(
        "/api/triggers/manual/dispatch",
        json={
            "workflow_id": str(missing_workflow),
            "actor": "tester",
            "runs": [{}],
        },
    )
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "Workflow not found"

    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Manual Errors", "actor": "author"},
    )
    workflow_id = workflow_response.json()["id"]

    no_version_response = api_client.post(
        "/api/triggers/manual/dispatch",
        json={
            "workflow_id": workflow_id,
            "actor": "tester",
            "runs": [{}],
        },
    )
    assert no_version_response.status_code == 404
    assert no_version_response.json()["detail"] == "Workflow version not found"
