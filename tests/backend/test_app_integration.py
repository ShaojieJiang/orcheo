"""Integration tests for backend API using TestClient."""

from __future__ import annotations
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from orcheo_backend.app import create_app
from orcheo_backend.app.history import InMemoryRunHistoryStore
from orcheo_backend.app.repository import InMemoryWorkflowRepository


@pytest.fixture
def repository():
    """Create an in-memory repository for testing."""
    return InMemoryWorkflowRepository()


@pytest.fixture
def history_store():
    """Create an in-memory history store for testing."""
    return InMemoryRunHistoryStore()


@pytest.fixture
def client(repository, history_store):
    """Create a test client with in-memory dependencies."""
    app = create_app(repository=repository, history_store=history_store)
    return TestClient(app)


def test_list_workflows_empty(client):
    """List workflows returns empty list initially."""
    response = client.get("/api/workflows")
    assert response.status_code == 200
    assert response.json() == []


def test_create_and_get_workflow(client):
    """Create and retrieve a workflow."""
    # Create workflow
    create_response = client.post(
        "/api/workflows",
        json={
            "name": "Test Workflow",
            "slug": "test-workflow",
            "description": "A test workflow",
            "tags": ["test"],
            "actor": "admin",
        },
    )
    assert create_response.status_code == 201
    workflow_data = create_response.json()
    workflow_id = workflow_data["id"]

    # Get workflow
    get_response = client.get(f"/api/workflows/{workflow_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Test Workflow"


def test_update_workflow(client):
    """Update workflow attributes."""
    # Create workflow first
    create_response = client.post(
        "/api/workflows",
        json={
            "name": "Original Name",
            "slug": "original-slug",
            "actor": "admin",
        },
    )
    workflow_id = create_response.json()["id"]

    # Update workflow
    update_response = client.put(
        f"/api/workflows/{workflow_id}",
        json={
            "name": "Updated Name",
            "description": "Updated description",
            "tags": ["updated"],
            "is_archived": False,
            "actor": "admin",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Name"


def test_archive_workflow(client):
    """Archive a workflow via DELETE."""
    # Create workflow first
    create_response = client.post(
        "/api/workflows",
        json={
            "name": "To Archive",
            "slug": "to-archive",
            "actor": "admin",
        },
    )
    workflow_id = create_response.json()["id"]

    # Archive workflow
    delete_response = client.delete(f"/api/workflows/{workflow_id}?actor=admin")
    assert delete_response.status_code == 200
    assert delete_response.json()["is_archived"] is True


def test_get_workflow_not_found(client):
    """Get non-existent workflow returns 404."""
    random_id = str(uuid4())
    response = client.get(f"/api/workflows/{random_id}")
    assert response.status_code == 404


def test_create_workflow_version(client):
    """Create a workflow version."""
    # Create workflow first
    workflow_response = client.post(
        "/api/workflows",
        json={
            "name": "Test Workflow",
            "slug": "test-workflow",
            "actor": "admin",
        },
    )
    workflow_id = workflow_response.json()["id"]

    # Create version
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


def test_list_workflow_versions(client):
    """List workflow versions."""
    # Create workflow and version
    workflow_response = client.post(
        "/api/workflows",
        json={
            "name": "Test Workflow",
            "slug": "test-workflow",
            "actor": "admin",
        },
    )
    workflow_id = workflow_response.json()["id"]

    client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {},
            "created_by": "admin",
        },
    )

    # List versions
    versions_response = client.get(f"/api/workflows/{workflow_id}/versions")
    assert versions_response.status_code == 200
    assert len(versions_response.json()) == 1


def test_get_workflow_version(client):
    """Get specific workflow version."""
    # Create workflow and version
    workflow_response = client.post(
        "/api/workflows",
        json={
            "name": "Test Workflow",
            "slug": "test-workflow",
            "actor": "admin",
        },
    )
    workflow_id = workflow_response.json()["id"]

    client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {},
            "created_by": "admin",
        },
    )

    # Get version by number
    version_response = client.get(f"/api/workflows/{workflow_id}/versions/1")
    assert version_response.status_code == 200
    assert version_response.json()["version"] == 1


def test_diff_workflow_versions(client):
    """Generate diff between workflow versions."""
    # Create workflow and two versions
    workflow_response = client.post(
        "/api/workflows",
        json={
            "name": "Test Workflow",
            "slug": "test-workflow",
            "actor": "admin",
        },
    )
    workflow_id = workflow_response.json()["id"]

    client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {"nodes": []},
            "created_by": "admin",
        },
    )

    client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {"nodes": ["node1"]},
            "created_by": "admin",
        },
    )

    # Get diff
    diff_response = client.get(f"/api/workflows/{workflow_id}/versions/1/diff/2")
    assert diff_response.status_code == 200
    assert diff_response.json()["base_version"] == 1
    assert diff_response.json()["target_version"] == 2


def test_list_workflow_execution_histories(client):
    """List execution histories for a workflow."""
    workflow_id = uuid4()

    # List histories (should be empty)
    response = client.get(f"/api/workflows/{workflow_id}/executions?limit=50")
    assert response.status_code == 200
    assert response.json() == []


def test_dispatch_cron_triggers(client):
    """Dispatch cron triggers."""
    response = client.post("/api/triggers/cron/dispatch")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_execute_node_missing_type(client):
    """Execute node without type field returns 400."""
    response = client.post(
        "/api/nodes/execute",
        json={
            "node_config": {"name": "test"},
            "inputs": {},
        },
    )
    assert response.status_code == 400
    assert "type" in response.json()["detail"]


def test_execute_node_unknown_type(client):
    """Execute node with unknown type returns 400."""
    response = client.post(
        "/api/nodes/execute",
        json={
            "node_config": {"type": "unknown_node_type", "name": "test"},
            "inputs": {},
        },
    )
    assert response.status_code == 400
    assert "Unknown node type" in response.json()["detail"]


def test_ingest_workflow_version_invalid_script(client):
    """Ingest invalid LangGraph script returns 400."""
    # Create workflow first
    workflow_response = client.post(
        "/api/workflows",
        json={
            "name": "Test Workflow",
            "slug": "test-workflow",
            "actor": "admin",
        },
    )
    workflow_id = workflow_response.json()["id"]

    # Try to ingest invalid script
    response = client.post(
        f"/api/workflows/{workflow_id}/versions/ingest",
        json={
            "script": "# Not a valid LangGraph script",
            "created_by": "admin",
        },
    )
    assert response.status_code == 400
