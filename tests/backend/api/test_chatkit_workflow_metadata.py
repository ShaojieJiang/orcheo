"""Tests for the public ChatKit workflow metadata endpoint."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import status
from fastapi.testclient import TestClient


@pytest.fixture(name="published_workflow")
def fixture_published_workflow(api_client: TestClient) -> tuple[UUID, str]:
    """Create and publish a workflow returning its id and token."""

    create_response = api_client.post(
        "/api/workflows",
        json={"name": "Public Workflow", "actor": "alice"},
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    workflow_id = UUID(create_response.json()["id"])

    publish_response = api_client.post(
        f"/api/workflows/{workflow_id}/publish",
        json={"require_login": True, "actor": "alice"},
    )
    assert publish_response.status_code == status.HTTP_201_CREATED
    token = publish_response.json()["publish_token"]
    assert token

    return workflow_id, token


def test_chatkit_metadata_requires_token(
    api_client: TestClient,
    published_workflow: tuple[UUID, str],
) -> None:
    workflow_id, _ = published_workflow

    response = api_client.get(f"/api/chatkit/workflows/{workflow_id}")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    detail = response.json()
    assert detail["detail"]["code"] == "chatkit.auth.publish_token_missing"


def test_chatkit_metadata_returns_payload(
    api_client: TestClient,
    published_workflow: tuple[UUID, str],
) -> None:
    workflow_id, token = published_workflow

    response = api_client.get(
        f"/api/chatkit/workflows/{workflow_id}",
        headers={"X-Orcheo-Publish-Token": token},
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["id"] == str(workflow_id)
    assert payload["name"] == "Public Workflow"
    assert payload["is_public"] is True
    assert payload["require_login"] is True


def test_chatkit_metadata_accepts_query_token(
    api_client: TestClient,
    published_workflow: tuple[UUID, str],
) -> None:
    workflow_id, token = published_workflow

    response = api_client.get(
        f"/api/chatkit/workflows/{workflow_id}?token={token}",
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["id"] == str(workflow_id)


def test_chatkit_metadata_rejects_invalid_token(
    api_client: TestClient,
    published_workflow: tuple[UUID, str],
) -> None:
    workflow_id, _ = published_workflow

    response = api_client.get(
        f"/api/chatkit/workflows/{workflow_id}",
        headers={"X-Orcheo-Publish-Token": "invalid-token"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    detail = response.json()
    assert detail["detail"]["code"] == "chatkit.auth.invalid_publish_token"


def test_chatkit_metadata_requires_public_state(
    api_client: TestClient,
    published_workflow: tuple[UUID, str],
) -> None:
    workflow_id, token = published_workflow

    revoke_response = api_client.post(
        f"/api/workflows/{workflow_id}/publish/revoke",
        json={"actor": "alice"},
    )
    assert revoke_response.status_code == status.HTTP_200_OK

    response = api_client.get(
        f"/api/chatkit/workflows/{workflow_id}",
        headers={"X-Orcheo-Publish-Token": token},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    detail = response.json()
    assert detail["detail"]["code"] == "chatkit.auth.not_published"
