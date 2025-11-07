"""Integration tests for assorted backend endpoints."""

from __future__ import annotations
from uuid import uuid4
from fastapi.testclient import TestClient


def test_list_workflow_execution_histories(client: TestClient) -> None:
    workflow_id = uuid4()
    response = client.get(f"/api/workflows/{workflow_id}/executions?limit=50")
    assert response.status_code == 200
    assert response.json() == []


def test_dispatch_cron_triggers(client: TestClient) -> None:
    response = client.post("/api/triggers/cron/dispatch")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_execute_node_missing_type(client: TestClient) -> None:
    response = client.post(
        "/api/nodes/execute",
        json={"node_config": {"name": "test"}, "inputs": {}},
    )
    assert response.status_code == 400
    assert "type" in response.json()["detail"]


def test_execute_node_unknown_type(client: TestClient) -> None:
    response = client.post(
        "/api/nodes/execute",
        json={
            "node_config": {"type": "unknown_node_type", "name": "test"},
            "inputs": {},
        },
    )
    assert response.status_code == 400
    assert "Unknown node type" in response.json()["detail"]
