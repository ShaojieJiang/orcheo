from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient

from .shared import create_workflow_with_version


def publish_workflow(
    api_client: TestClient, workflow_id: str, *, require_login: bool
) -> None:
    response = api_client.post(
        f"/api/workflows/{workflow_id}/publish",
        json={"require_login": require_login, "actor": "tester"},
    )
    response.raise_for_status()


def test_get_public_workflow_metadata_returns_publish_state(
    api_client: TestClient,
) -> None:
    """Published workflows expose minimal metadata for the chat page."""

    workflow_id, _ = create_workflow_with_version(api_client)
    publish_workflow(api_client, workflow_id, require_login=False)

    response = api_client.get(f"/api/chatkit/workflows/{workflow_id}")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["id"] == workflow_id
    assert payload["name"] == "Webhook Flow"
    assert payload["is_public"] is True
    assert payload["require_login"] is False


def test_get_public_workflow_metadata_marks_login_requirement(
    api_client: TestClient,
) -> None:
    """The response reflects when OAuth login is required."""

    workflow_id, _ = create_workflow_with_version(api_client)
    publish_workflow(api_client, workflow_id, require_login=True)

    response = api_client.get(f"/api/chatkit/workflows/{workflow_id}")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["require_login"] is True


def test_get_public_workflow_metadata_rejects_unpublished_workflows(
    api_client: TestClient,
) -> None:
    """Unpublished workflows do not leak metadata."""

    workflow_id, _ = create_workflow_with_version(api_client)

    response = api_client.get(f"/api/chatkit/workflows/{workflow_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_public_workflow_metadata_handles_missing_workflow(
    api_client: TestClient,
) -> None:
    """Missing workflows return a 404 response."""

    response = api_client.get(f"/api/chatkit/workflows/{uuid4()}")

    assert response.status_code == status.HTTP_404_NOT_FOUND
