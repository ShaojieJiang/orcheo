"""End-to-end API tests for the Orcheo FastAPI backend."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from orcheo_backend.app import create_app
from orcheo_backend.app.repository import InMemoryWorkflowRepository


@pytest.fixture()
def api_client() -> Iterator[TestClient]:
    """Yield a configured API client backed by a fresh repository."""

    repository = InMemoryWorkflowRepository()
    app = create_app(repository)
    with TestClient(app) as client:
        yield client


def test_workflow_crud_operations(api_client: TestClient) -> None:
    """Validate workflow creation, retrieval, update, and archival."""

    create_response = api_client.post(
        "/api/workflows",
        json={
            "name": "Sample Flow",
            "description": "Initial description",
            "tags": ["Demo", "Example"],
            "actor": "tester",
        },
    )
    assert create_response.status_code == 201
    workflow = create_response.json()
    workflow_id = workflow["id"]
    assert workflow["slug"] == "sample-flow"

    get_response = api_client.get(f"/api/workflows/{workflow_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Sample Flow"

    update_response = api_client.put(
        f"/api/workflows/{workflow_id}",
        json={"description": "Updated description", "actor": "tester"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["description"] == "Updated description"

    list_response = api_client.get("/api/workflows")
    assert list_response.status_code == 200
    assert any(item["id"] == workflow_id for item in list_response.json())

    delete_response = api_client.delete(
        f"/api/workflows/{workflow_id}",
        params={"actor": "tester"},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["is_archived"] is True


def test_workflow_versions_and_diff(api_client: TestClient) -> None:
    """Ensure version creation, retrieval, and diffing all function."""

    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Diff Flow", "actor": "author"},
    )
    workflow = workflow_response.json()
    workflow_id = workflow["id"]

    version_one = api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {"nodes": ["start"], "edges": []},
            "metadata": {"notes": "v1"},
            "created_by": "author",
        },
    )
    assert version_one.status_code == 201
    version_two = api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {
                "nodes": ["start", "end"],
                "edges": [{"from": "start", "to": "end"}],
            },
            "metadata": {"notes": "v2"},
            "created_by": "author",
            "notes": "Adds end node",
        },
    )
    assert version_two.status_code == 201

    list_versions = api_client.get(f"/api/workflows/{workflow_id}/versions")
    assert list_versions.status_code == 200
    versions = list_versions.json()
    assert [version["version"] for version in versions] == [1, 2]

    version_detail = api_client.get(f"/api/workflows/{workflow_id}/versions/2")
    assert version_detail.status_code == 200
    assert version_detail.json()["version"] == 2

    diff_response = api_client.get(f"/api/workflows/{workflow_id}/versions/1/diff/2")
    assert diff_response.status_code == 200
    diff_payload = diff_response.json()
    assert diff_payload["base_version"] == 1
    assert diff_payload["target_version"] == 2
    diff_lines = diff_payload["diff"]
    assert any('+    "end"' in line for line in diff_lines)


def test_workflow_run_lifecycle(api_client: TestClient) -> None:
    """Exercise the workflow run state transitions."""

    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Run Flow", "actor": "runner"},
    )
    workflow_id = workflow_response.json()["id"]

    version_response = api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {"nodes": ["start"], "edges": []},
            "metadata": {},
            "created_by": "runner",
        },
    )
    version_id = UUID(version_response.json()["id"])

    run_response = api_client.post(
        f"/api/workflows/{workflow_id}/runs",
        json={
            "workflow_version_id": str(version_id),
            "triggered_by": "runner",
            "input_payload": {"input": "value"},
        },
    )
    assert run_response.status_code == 201
    run_payload = run_response.json()
    run_id = run_payload["id"]
    assert run_payload["status"] == "pending"

    start_response = api_client.post(
        f"/api/runs/{run_id}/start",
        json={"actor": "runner"},
    )
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"

    succeed_response = api_client.post(
        f"/api/runs/{run_id}/succeed",
        json={"actor": "runner", "output": {"result": "ok"}},
    )
    assert succeed_response.status_code == 200
    succeeded_payload = succeed_response.json()
    assert succeeded_payload["status"] == "succeeded"
    assert succeeded_payload["output_payload"]["result"] == "ok"

    list_runs_response = api_client.get(f"/api/workflows/{workflow_id}/runs")
    assert list_runs_response.status_code == 200
    run_ids = [run["id"] for run in list_runs_response.json()]
    assert run_id in run_ids

    run_detail = api_client.get(f"/api/runs/{run_id}")
    assert run_detail.status_code == 200
    assert run_detail.json()["status"] == "succeeded"
