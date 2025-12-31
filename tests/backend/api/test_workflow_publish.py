from __future__ import annotations
from uuid import UUID
import pytest
from fastapi.testclient import TestClient
from orcheo.config import get_settings


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
    assert payload["message"]

    workflow = payload["workflow"]
    assert workflow["is_public"] is True
    assert workflow["require_login"] is True
    assert workflow["published_by"] == "alice"
    assert workflow["published_at"] is not None

    fetched = api_client.get(f"/api/workflows/{workflow_id}")
    assert fetched.status_code == 200
    fetched_payload = fetched.json()
    assert fetched_payload["is_public"] is True
    assert fetched_payload["published_at"] == workflow["published_at"]


def test_publish_workflow_includes_share_url(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "ORCHEO_CHATKIT_PUBLIC_BASE_URL",
        "https://orcheo-canvas.ai-colleagues.com",
    )
    get_settings(refresh=True)

    workflow_id = _create_workflow(api_client)
    response = api_client.post(
        f"/api/workflows/{workflow_id}/publish",
        json={"require_login": False, "actor": "alice"},
    )

    assert response.status_code == 201
    payload = response.json()
    expected_url = f"https://orcheo-canvas.ai-colleagues.com/chat/{workflow_id}"
    assert payload["share_url"] == expected_url
    assert payload["workflow"]["share_url"] == expected_url

    fetched = api_client.get(f"/api/workflows/{workflow_id}")
    assert fetched.status_code == 200
    assert fetched.json()["share_url"] == expected_url


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
