from __future__ import annotations
from datetime import UTC, datetime
from uuid import uuid4
from fastapi.testclient import TestClient
from .shared import create_workflow_with_version


def test_cron_trigger_config_endpoints_require_known_workflow(
    api_client: TestClient,
) -> None:
    """Cron configuration endpoints return 404 for unknown workflows."""

    missing_id = uuid4()

    update_response = api_client.put(
        f"/api/workflows/{missing_id}/triggers/cron/config",
        json={
            "expression": "0 12 * * *",
            "timezone": "UTC",
            "allow_overlapping": False,
        },
    )
    assert update_response.status_code == 404
    assert update_response.json()["detail"] == "Workflow not found"

    fetch_response = api_client.get(f"/api/workflows/{missing_id}/triggers/cron/config")
    assert fetch_response.status_code == 404
    assert fetch_response.json()["detail"] == "Workflow not found"


def test_cron_trigger_configuration_roundtrip(api_client: TestClient) -> None:
    """Cron trigger configuration can be updated and retrieved."""

    workflow_id, _ = create_workflow_with_version(api_client)

    default_response = api_client.get(
        f"/api/workflows/{workflow_id}/triggers/cron/config"
    )
    assert default_response.status_code == 200
    assert default_response.json()["expression"] == "0 * * * *"

    update_response = api_client.put(
        f"/api/workflows/{workflow_id}/triggers/cron/config",
        json={
            "expression": "0 9 * * MON-FRI",
            "timezone": "America/New_York",
            "allow_overlapping": False,
        },
    )
    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["expression"] == "0 9 * * MON-FRI"
    assert payload["timezone"] == "America/New_York"
    assert payload["allow_overlapping"] is False

    roundtrip = api_client.get(f"/api/workflows/{workflow_id}/triggers/cron/config")
    assert roundtrip.status_code == 200
    assert roundtrip.json() == payload


def test_cron_trigger_delete_endpoint(api_client: TestClient) -> None:
    """Deleting a cron trigger removes the configuration."""

    workflow_id, _ = create_workflow_with_version(api_client)
    api_client.put(
        f"/api/workflows/{workflow_id}/triggers/cron/config",
        json={
            "expression": "0 9 * * *",
            "timezone": "UTC",
        },
    )

    delete_response = api_client.delete(
        f"/api/workflows/{workflow_id}/triggers/cron/config"
    )
    assert delete_response.status_code == 204


def test_cron_trigger_delete_missing_workflow(api_client: TestClient) -> None:
    """Deleting a cron trigger returns 404 when the workflow is unknown."""

    missing_id = uuid4()
    delete_response = api_client.delete(
        f"/api/workflows/{missing_id}/triggers/cron/config"
    )
    assert delete_response.status_code == 404
    assert delete_response.json()["detail"] == "Workflow not found"


def test_cron_trigger_dispatch_and_overlap(api_client: TestClient) -> None:
    """Cron dispatch endpoint enqueues due runs and enforces overlap guard."""

    workflow_id, _ = create_workflow_with_version(api_client)

    api_client.put(
        f"/api/workflows/{workflow_id}/triggers/cron/config",
        json={
            "expression": "0 9 * * *",
            "timezone": "UTC",
            "allow_overlapping": False,
        },
    )

    dispatch_response = api_client.post(
        "/api/triggers/cron/dispatch",
        json={"now": datetime(2025, 1, 1, 9, 0, tzinfo=UTC).isoformat()},
    )
    assert dispatch_response.status_code == 200
    runs = dispatch_response.json()
    assert len(runs) == 1
    run_id = runs[0]["id"]
    assert runs[0]["triggered_by"] == "cron"

    blocked = api_client.post(
        "/api/triggers/cron/dispatch",
        json={"now": datetime(2025, 1, 1, 10, 0, tzinfo=UTC).isoformat()},
    )
    assert blocked.status_code == 200
    assert blocked.json() == []

    start_response = api_client.post(
        f"/api/runs/{run_id}/start",
        json={"actor": "cron"},
    )
    assert start_response.status_code == 200

    succeed_response = api_client.post(
        f"/api/runs/{run_id}/succeed",
        json={"actor": "cron"},
    )
    assert succeed_response.status_code == 200

    next_dispatch = api_client.post(
        "/api/triggers/cron/dispatch",
        json={"now": datetime(2025, 1, 2, 9, 0, tzinfo=UTC).isoformat()},
    )
    assert next_dispatch.status_code == 200
    assert len(next_dispatch.json()) == 1


def test_cron_trigger_timezone_dispatch(api_client: TestClient) -> None:
    """Cron dispatch respects configured timezones."""

    workflow_id, _ = create_workflow_with_version(api_client)

    api_client.put(
        f"/api/workflows/{workflow_id}/triggers/cron/config",
        json={
            "expression": "0 9 * * *",
            "timezone": "America/Los_Angeles",
        },
    )

    dispatch_response = api_client.post(
        "/api/triggers/cron/dispatch",
        json={"now": datetime(2025, 1, 1, 17, 0, tzinfo=UTC).isoformat()},
    )
    assert dispatch_response.status_code == 200
    assert len(dispatch_response.json()) == 1


def test_manual_trigger_dispatch_single_run(api_client: TestClient) -> None:
    """Manual trigger endpoint creates a run with the latest version."""

    workflow_id, _ = create_workflow_with_version(api_client)

    dispatch_response = api_client.post(
        "/api/triggers/manual/dispatch",
        json={
            "workflow_id": workflow_id,
            "actor": "operator",
            "runs": [{"input_payload": {"foo": "bar"}}],
        },
    )
    assert dispatch_response.status_code == 200
    runs = dispatch_response.json()
    assert len(runs) == 1
    run = runs[0]
    assert run["triggered_by"] == "manual"
    assert run["input_payload"] == {"foo": "bar"}

    detail_response = api_client.get(f"/api/runs/{run['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["audit_log"][0]["actor"] == "operator"


def test_manual_trigger_dispatch_batch(api_client: TestClient) -> None:
    """Batch manual dispatch honors explicit version overrides."""

    workflow_id, version_one = create_workflow_with_version(api_client)
    version_two_response = api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {"nodes": ["start", "branch"], "edges": []},
            "metadata": {},
            "created_by": "tester",
        },
    )
    assert version_two_response.status_code == 201
    version_two = version_two_response.json()["id"]

    dispatch_response = api_client.post(
        "/api/triggers/manual/dispatch",
        json={
            "workflow_id": workflow_id,
            "actor": "batcher",
            "runs": [
                {
                    "workflow_version_id": version_one,
                    "input_payload": {"index": 1},
                },
                {
                    "workflow_version_id": version_two,
                    "input_payload": {"index": 2},
                },
            ],
        },
    )
    assert dispatch_response.status_code == 200
    runs = dispatch_response.json()
    assert [run["triggered_by"] for run in runs] == ["manual_batch", "manual_batch"]
    assert [run["workflow_version_id"] for run in runs] == [
        version_one,
        version_two,
    ]


def test_manual_trigger_dispatch_errors(api_client: TestClient) -> None:
    """Manual dispatch returns 404 when workflow or versions are missing."""

    missing_workflow = uuid4()
    missing_response = api_client.post(
        "/api/triggers/manual/dispatch",
        json={
            "workflow_id": str(missing_workflow),
            "actor": "tester",
            "runs": [{}],
        },
    )
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "Workflow not found"

    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Manual Errors", "actor": "author"},
    )
    workflow_id = workflow_response.json()["id"]

    no_version_response = api_client.post(
        "/api/triggers/manual/dispatch",
        json={
            "workflow_id": workflow_id,
            "actor": "tester",
            "runs": [{}],
        },
    )
    assert no_version_response.status_code == 404
    assert no_version_response.json()["detail"] == "Workflow version not found"
