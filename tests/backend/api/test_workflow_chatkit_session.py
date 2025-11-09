"""HTTP regression tests for the workflow ChatKit session endpoint."""

from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from orcheo_backend.app.chatkit_tokens import reset_chatkit_token_state


def _create_workflow(client: TestClient) -> str:
    response = client.post(
        "/api/workflows",
        json={"name": "Canvas Workflow", "actor": "tester"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_chatkit_session_requires_authentication_http(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anonymous requests should receive a 401 instead of a server error."""
    monkeypatch.setenv("ORCHEO_CHATKIT_TOKEN_SIGNING_KEY", "workflow-session-key")
    reset_chatkit_token_state()

    workflow_id = _create_workflow(api_client)

    response = api_client.post(f"/api/workflows/{workflow_id}/chatkit/session")

    assert response.status_code == 401
    payload = response.json()
    assert payload["detail"]["code"] == "auth.authentication_required"
