"""End-to-end API tests for the Orcheo FastAPI backend."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID, uuid4

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


def test_workflow_run_invalid_transitions(api_client: TestClient) -> None:
    """Invalid run transitions return conflict responses with helpful details."""

    workflow = api_client.post(
        "/api/workflows",
        json={"name": "Conflict Flow", "actor": "runner"},
    ).json()
    workflow_id = workflow["id"]

    version = api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={"graph": {}, "metadata": {}, "created_by": "runner"},
    ).json()

    run = api_client.post(
        f"/api/workflows/{workflow_id}/runs",
        json={
            "workflow_version_id": version["id"],
            "triggered_by": "runner",
            "input_payload": {},
        },
    ).json()
    run_id = run["id"]

    succeed_before_start = api_client.post(
        f"/api/runs/{run_id}/succeed",
        json={"actor": "runner", "output": {}},
    )
    assert succeed_before_start.status_code == 409
    assert (
        succeed_before_start.json()["detail"]
        == "Only running runs can be marked as succeeded."
    )

    start_response = api_client.post(
        f"/api/runs/{run_id}/start",
        json={"actor": "runner"},
    )
    assert start_response.status_code == 200

    restart_response = api_client.post(
        f"/api/runs/{run_id}/start",
        json={"actor": "runner"},
    )
    assert restart_response.status_code == 409
    assert restart_response.json()["detail"] == "Only pending runs can be started."

    succeed_response = api_client.post(
        f"/api/runs/{run_id}/succeed",
        json={"actor": "runner", "output": {"result": "ok"}},
    )
    assert succeed_response.status_code == 200

    cancel_after_completion = api_client.post(
        f"/api/runs/{run_id}/cancel",
        json={"actor": "runner", "reason": None},
    )
    assert cancel_after_completion.status_code == 409
    assert (
        cancel_after_completion.json()["detail"]
        == "Cannot cancel a run that is already completed."
    )


def test_not_found_responses(api_client: TestClient) -> None:
    """The API surfaces standardized 404 errors when entities are missing."""

    missing_id = "00000000-0000-0000-0000-000000000000"

    workflow_response = api_client.get(f"/api/workflows/{missing_id}")
    assert workflow_response.status_code == 404
    assert workflow_response.json()["detail"] == "Workflow not found"

    run_response = api_client.get(f"/api/runs/{missing_id}")
    assert run_response.status_code == 404
    assert run_response.json()["detail"] == "Workflow run not found"


def test_version_and_run_error_responses(api_client: TestClient) -> None:
    """Version and run routes propagate repository errors as 404 responses."""

    missing = str(uuid4())

    update_response = api_client.put(
        f"/api/workflows/{missing}", json={"actor": "tester"}
    )
    assert update_response.status_code == 404

    delete_response = api_client.delete(
        f"/api/workflows/{missing}", params={"actor": "tester"}
    )
    assert delete_response.status_code == 404

    create_version_missing = api_client.post(
        f"/api/workflows/{missing}/versions",
        json={
            "graph": {},
            "metadata": {},
            "created_by": "tester",
        },
    )
    assert create_version_missing.status_code == 404

    list_versions_missing = api_client.get(f"/api/workflows/{missing}/versions")
    assert list_versions_missing.status_code == 404

    missing_version_for_missing_workflow = api_client.get(
        f"/api/workflows/{missing}/versions/1"
    )
    assert missing_version_for_missing_workflow.status_code == 404

    workflow = api_client.post(
        "/api/workflows",
        json={"name": "Error Flow", "actor": "tester"},
    ).json()
    workflow_id = workflow["id"]

    api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={"graph": {}, "metadata": {}, "created_by": "tester"},
    )

    missing_version_response = api_client.get(
        f"/api/workflows/{workflow_id}/versions/99"
    )
    assert missing_version_response.status_code == 404
    assert missing_version_response.json()["detail"] == "Workflow version not found"

    diff_missing_version = api_client.get(
        f"/api/workflows/{workflow_id}/versions/1/diff/99"
    )
    assert diff_missing_version.status_code == 404

    diff_missing_workflow = api_client.get(
        f"/api/workflows/{missing}/versions/1/diff/1"
    )
    assert diff_missing_workflow.status_code == 404
    assert diff_missing_workflow.json()["detail"] == "Workflow not found"

    create_run_missing_version = api_client.post(
        f"/api/workflows/{workflow_id}/runs",
        json={
            "workflow_version_id": str(uuid4()),
            "triggered_by": "tester",
            "input_payload": {},
        },
    )
    assert create_run_missing_version.status_code == 404
    assert create_run_missing_version.json()["detail"] == "Workflow version not found"

    create_run_missing_workflow = api_client.post(
        f"/api/workflows/{missing}/runs",
        json={
            "workflow_version_id": str(uuid4()),
            "triggered_by": "tester",
            "input_payload": {},
        },
    )
    assert create_run_missing_workflow.status_code == 404
    assert create_run_missing_workflow.json()["detail"] == "Workflow not found"

    list_runs_missing = api_client.get(f"/api/workflows/{missing}/runs")
    assert list_runs_missing.status_code == 404

    for endpoint in [
        "start",
        "succeed",
        "fail",
        "cancel",
    ]:
        payload: dict[str, object] = {"actor": "tester"}
        if endpoint == "succeed":
            payload["output"] = None
        if endpoint == "fail":
            payload["error"] = "boom"
        if endpoint == "cancel":
            payload["reason"] = None
        response = api_client.post(
            f"/api/runs/{missing}/{endpoint}",
            json=payload,
        )
        assert response.status_code == 404
