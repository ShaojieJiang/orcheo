from __future__ import annotations
from uuid import UUID, uuid4
from fastapi.testclient import TestClient


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
            "input_payload": {},
        },
    )
    assert run_response.status_code == 201
    run = run_response.json()
    run_id = run["id"]
    assert run["status"] == "pending"

    start_response = api_client.post(
        f"/api/runs/{run_id}/start",
        json={"actor": "runner"},
    )
    assert start_response.status_code == 200

    succeed_response = api_client.post(
        f"/api/runs/{run_id}/succeed",
        json={"actor": "runner", "output": {"result": "ok"}},
    )
    assert succeed_response.status_code == 200

    history_response = api_client.get(f"/api/runs/{run_id}")
    assert history_response.status_code == 200
    history = history_response.json()
    assert history["status"] == "succeeded"
    assert history["audit_log"][-1]["actor"] == "runner"


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

    fail_after_completion = api_client.post(
        f"/api/runs/{run_id}/fail",
        json={"actor": "runner", "error": "boom"},
    )
    assert fail_after_completion.status_code == 409
    assert (
        fail_after_completion.json()["detail"]
        == "Only pending or running runs can be marked as failed."
    )

    cancel_after_completion = api_client.post(
        f"/api/runs/{run_id}/cancel",
        json={"actor": "runner", "reason": None},
    )
    assert cancel_after_completion.status_code == 409
    assert (
        cancel_after_completion.json()["detail"]
        == "Cannot cancel a run that is already completed."
    )


def test_create_run_rejects_archived_workflow(api_client: TestClient) -> None:
    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Archived Flow", "actor": "runner"},
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
    version_id = version_response.json()["id"]

    archive_response = api_client.delete(
        f"/api/workflows/{workflow_id}",
        params={"actor": "runner"},
    )
    assert archive_response.status_code == 200

    run_response = api_client.post(
        f"/api/workflows/{workflow_id}/runs",
        json={
            "workflow_version_id": version_id,
            "triggered_by": "runner",
            "input_payload": {},
        },
    )
    assert run_response.status_code == 404


def test_not_found_responses(api_client: TestClient) -> None:
    """Missing workflows and runs return uniform 404 responses."""

    missing = uuid4()

    fetch_missing_workflow = api_client.get(f"/api/workflows/{missing}")
    assert fetch_missing_workflow.status_code == 404

    delete_missing_workflow = api_client.delete(
        f"/api/workflows/{missing}",
        params={"actor": "tester"},
    )
    assert delete_missing_workflow.status_code == 404

    create_version_missing = api_client.post(
        f"/api/workflows/{missing}/versions",
        json={"graph": {}, "metadata": {}, "created_by": "tester"},
    )
    assert create_version_missing.status_code == 404

    list_versions_missing = api_client.get(f"/api/workflows/{missing}/versions")
    assert list_versions_missing.status_code == 404

    missing_version_for_missing_workflow = api_client.get(
        f"/api/workflows/{missing}/versions/1"
    )
    assert missing_version_for_missing_workflow.status_code == 404


def test_version_and_run_error_responses(api_client: TestClient) -> None:
    """Version-specific endpoints surface clear error messages."""

    missing = uuid4()

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
