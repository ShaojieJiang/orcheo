"""Integration tests for workflow version endpoints."""

from __future__ import annotations
from fastapi.testclient import TestClient


def test_create_workflow_version(client: TestClient) -> None:
    workflow_response = client.post(
        "/api/workflows",
        json={"name": "Test Workflow", "slug": "test-workflow", "actor": "admin"},
    )
    workflow_id = workflow_response.json()["id"]

    version_response = client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {"nodes": [], "edges": []},
            "metadata": {"test": "data"},
            "notes": "Initial version",
            "created_by": "admin",
        },
    )
    assert version_response.status_code == 201
    assert version_response.json()["version"] == 1
    assert isinstance(version_response.json()["mermaid"], str)


def test_list_workflow_versions(client: TestClient) -> None:
    workflow_response = client.post(
        "/api/workflows",
        json={"name": "Test Workflow", "slug": "test-workflow", "actor": "admin"},
    )
    workflow_id = workflow_response.json()["id"]

    client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={"graph": {}, "created_by": "admin"},
    )

    versions_response = client.get(f"/api/workflows/{workflow_id}/versions")
    assert versions_response.status_code == 200
    assert len(versions_response.json()) == 1
    assert isinstance(versions_response.json()[0]["mermaid"], str)


def test_get_workflow_version(client: TestClient) -> None:
    workflow_response = client.post(
        "/api/workflows",
        json={"name": "Test Workflow", "slug": "test-workflow", "actor": "admin"},
    )
    workflow_id = workflow_response.json()["id"]

    client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={"graph": {}, "created_by": "admin"},
    )

    version_response = client.get(f"/api/workflows/{workflow_id}/versions/1")
    assert version_response.status_code == 200
    assert version_response.json()["version"] == 1
    assert isinstance(version_response.json()["mermaid"], str)


def test_diff_workflow_versions(client: TestClient) -> None:
    workflow_response = client.post(
        "/api/workflows",
        json={"name": "Test Workflow", "slug": "test-workflow", "actor": "admin"},
    )
    workflow_id = workflow_response.json()["id"]

    client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={"graph": {"nodes": []}, "created_by": "admin"},
    )
    client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={"graph": {"nodes": ["node1"]}, "created_by": "admin"},
    )

    diff_response = client.get(f"/api/workflows/{workflow_id}/versions/1/diff/2")
    assert diff_response.status_code == 200
    assert diff_response.json()["base_version"] == 1
    assert diff_response.json()["target_version"] == 2


def test_ingest_workflow_version_invalid_script(client: TestClient) -> None:
    workflow_response = client.post(
        "/api/workflows",
        json={"name": "Test Workflow", "slug": "test-workflow", "actor": "admin"},
    )
    workflow_id = workflow_response.json()["id"]

    response = client.post(
        f"/api/workflows/{workflow_id}/versions/ingest",
        json={"script": "# Not a valid LangGraph script", "created_by": "admin"},
    )
    assert response.status_code == 400
