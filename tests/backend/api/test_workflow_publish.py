from __future__ import annotations
from uuid import UUID
from fastapi.testclient import TestClient


def _create_workflow(client: TestClient) -> UUID:
    response = client.post(
        "/api/workflows",
        json={"name": "Publish Workflow", "actor": "tester"},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def test_publish_workflow_sets_metadata(api_client: TestClient) -> None:
    workflow_id = _create_workflow(api_client)

    response = api_client.post(
        f"/api/workflows/{workflow_id}/publish",
        json={"require_login": True, "actor": "alice"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["publish_token"]
    assert payload["message"]

    workflow = payload["workflow"]
    assert workflow["is_public"] is True
    assert workflow["require_login"] is True
    assert workflow["published_by"] == "alice"
    assert workflow["publish_token_hash"]

    fetched = api_client.get(f"/api/workflows/{workflow_id}")
    assert fetched.status_code == 200
    fetched_payload = fetched.json()
    assert fetched_payload["is_public"] is True
    assert fetched_payload["publish_token_hash"] == workflow["publish_token_hash"]


def test_rotate_publish_token(api_client: TestClient) -> None:
    workflow_id = _create_workflow(api_client)

    publish_response = api_client.post(f"/api/workflows/{workflow_id}/publish", json={})
    first_token = publish_response.json()["publish_token"]

    rotate_response = api_client.post(
        f"/api/workflows/{workflow_id}/publish/rotate",
        json={"actor": "rotator"},
    )

    assert rotate_response.status_code == 200
    rotated_payload = rotate_response.json()
    assert rotated_payload["publish_token"]
    assert rotated_payload["publish_token"] != first_token
    assert rotated_payload["workflow"]["publish_token_rotated_at"] is not None


def test_revoke_publish_resets_state(api_client: TestClient) -> None:
    workflow_id = _create_workflow(api_client)

    api_client.post(f"/api/workflows/{workflow_id}/publish", json={})

    revoke_response = api_client.post(
        f"/api/workflows/{workflow_id}/publish/revoke",
        json={"actor": "revoker"},
    )

    assert revoke_response.status_code == 200
    workflow = revoke_response.json()
    assert workflow["is_public"] is False
    assert workflow["publish_token_hash"] is None
    assert workflow["require_login"] is False


def test_publish_invalid_state_returns_conflict(api_client: TestClient) -> None:
    workflow_id = _create_workflow(api_client)

    assert (
        api_client.post(f"/api/workflows/{workflow_id}/publish", json={}).status_code
        == 201
    )
    conflict = api_client.post(
        f"/api/workflows/{workflow_id}/publish",
        json={},
    )
    assert conflict.status_code == 409
    detail = conflict.json()
    assert detail["detail"]["code"] == "workflow.publish.invalid_state"
