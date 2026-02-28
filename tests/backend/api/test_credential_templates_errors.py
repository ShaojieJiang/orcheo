from __future__ import annotations
from uuid import uuid4
from fastapi.testclient import TestClient


def _create_workflow(api_client: TestClient) -> str:
    response = api_client.post(
        "/api/workflows",
        json={"name": "Template Flow", "actor": "tester"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_credential_template_get_scope_violation_returns_403(
    api_client: TestClient,
) -> None:
    workflow_id = _create_workflow(api_client)
    other_workflow_id = _create_workflow(api_client)
    create_response = api_client.post(
        "/api/credentials/templates",
        json={
            "name": "Restricted",
            "provider": "internal",
            "scopes": ["read"],
            "scope": {"workflow_ids": [workflow_id]},
            "actor": "tester",
        },
    )
    template_id = create_response.json()["id"]

    response = api_client.get(
        f"/api/credentials/templates/{template_id}",
        params={"workflow_id": other_workflow_id},
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
    workflow_id = _create_workflow(api_client)
    other_workflow_id = _create_workflow(api_client)
    create_response = api_client.post(
        "/api/credentials/templates",
        json={
            "name": "Restricted",
            "provider": "internal",
            "scopes": ["read"],
            "scope": {"workflow_ids": [workflow_id]},
            "actor": "tester",
        },
    )
    template_id = create_response.json()["id"]

    response = api_client.patch(
        f"/api/credentials/templates/{template_id}",
        params={"workflow_id": other_workflow_id},
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
    workflow_id = _create_workflow(api_client)
    other_workflow_id = _create_workflow(api_client)
    create_response = api_client.post(
        "/api/credentials/templates",
        json={
            "name": "Restricted",
            "provider": "internal",
            "scopes": ["read"],
            "scope": {"workflow_ids": [workflow_id]},
            "actor": "tester",
        },
    )
    template_id = create_response.json()["id"]

    response = api_client.delete(
        f"/api/credentials/templates/{template_id}",
        params={"workflow_id": other_workflow_id},
    )

    assert response.status_code == 403
