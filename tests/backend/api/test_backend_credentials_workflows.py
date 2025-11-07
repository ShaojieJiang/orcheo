"""Credential and workflow coverage tests for orcheo_backend.app."""

from __future__ import annotations
import importlib
from typing import Any
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient


backend_app = importlib.import_module("orcheo_backend.app")


@pytest.mark.asyncio
async def test_credential_health_get_without_service(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Credential health endpoint returns 503 when service missing."""
    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Test Flow", "actor": "tester"},
    )
    workflow_id = workflow_response.json()["id"]

    monkeypatch.setitem(backend_app._credential_service_ref, "service", None)
    api_client.app.dependency_overrides[backend_app.get_credential_service] = (
        lambda: None
    )

    response = api_client.get(f"/api/workflows/{workflow_id}/credentials/health")
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


@pytest.mark.asyncio
async def test_credential_health_validate_without_service(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Credential validation endpoint returns 503 when service missing."""
    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Test Flow", "actor": "tester"},
    )
    workflow_id = workflow_response.json()["id"]

    monkeypatch.setitem(backend_app._credential_service_ref, "service", None)
    api_client.app.dependency_overrides[backend_app.get_credential_service] = (
        lambda: None
    )

    response = api_client.post(
        f"/api/workflows/{workflow_id}/credentials/validate",
        json={"actor": "tester"},
    )
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_delete_credential_not_found(api_client: TestClient) -> None:
    """Deleting a non-existent credential returns 404."""
    missing_id = uuid4()
    response = api_client.delete(f"/api/credentials/{missing_id}")
    assert response.status_code == 404


def test_delete_credential_scope_violation(api_client: TestClient) -> None:
    """Deleting credential with mismatched workflow raises 403."""
    workflow_id = uuid4()
    other_workflow_id = uuid4()

    create_response = api_client.post(
        "/api/credentials",
        json={
            "name": "Scoped Cred",
            "provider": "test",
            "secret": "secret",
            "actor": "tester",
            "access": "private",
            "workflow_id": str(workflow_id),
        },
    )
    credential_id = create_response.json()["id"]

    response = api_client.delete(
        f"/api/credentials/{credential_id}",
        params={"workflow_id": str(other_workflow_id)},
    )
    assert response.status_code == 403


def test_create_credential_with_value_error(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Backend surfaces ValueError from credential vault as 422."""
    vault = api_client.app.state.vault

    def mock_create_credential(*args: Any, **kwargs: Any) -> None:
        raise ValueError("Invalid credential configuration")

    monkeypatch.setattr(vault, "create_credential", mock_create_credential)

    response = api_client.post(
        "/api/credentials",
        json={
            "name": "Test Cred",
            "provider": "test",
            "secret": "secret",
            "actor": "tester",
            "access": "public",
            "kind": "secret",
        },
    )
    assert response.status_code == 422


def test_list_workflows_includes_archived(api_client: TestClient) -> None:
    """Workflows endpoint optionally returns archived entries."""
    create_response = api_client.post(
        "/api/workflows",
        json={"name": "To Archive", "actor": "tester"},
    )
    workflow_id = create_response.json()["id"]

    api_client.delete(f"/api/workflows/{workflow_id}", params={"actor": "tester"})

    response = api_client.get("/api/workflows")
    assert workflow_id not in [w["id"] for w in response.json()]

    response = api_client.get("/api/workflows?include_archived=true")
    assert any(w["id"] == workflow_id for w in response.json())


def test_ingest_workflow_version_script_error(api_client: TestClient) -> None:
    """Ingest endpoint returns 400 for bad script payloads."""
    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Bad Script", "actor": "tester"},
    )
    workflow_id = workflow_response.json()["id"]

    response = api_client.post(
        f"/api/workflows/{workflow_id}/versions/ingest",
        json={
            "script": "invalid python code!!!",
            "entrypoint": "app",
            "created_by": "tester",
        },
    )
    assert response.status_code == 400
