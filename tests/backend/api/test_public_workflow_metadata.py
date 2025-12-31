from __future__ import annotations
from uuid import UUID
from fastapi.testclient import TestClient


def _create_workflow(client: TestClient) -> UUID:
    response = client.post(
        "/api/workflows",
        json={"name": "Public Metadata Workflow", "actor": "tester"},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def test_public_workflow_metadata_requires_public_workflow(
    api_client: TestClient,
) -> None:
    workflow_id = _create_workflow(api_client)

    response = api_client.get(f"/api/workflows/{workflow_id}/public")

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "workflow.not_public"


def test_public_workflow_metadata_returns_published_workflow(
    api_client: TestClient,
) -> None:
    workflow_id = _create_workflow(api_client)
    publish_response = api_client.post(
        f"/api/workflows/{workflow_id}/publish",
        json={"require_login": True, "actor": "publisher"},
    )
    assert publish_response.status_code == 201

    response = api_client.get(f"/api/workflows/{workflow_id}/public")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(workflow_id)
    assert payload["is_public"] is True
    assert payload["require_login"] is True
