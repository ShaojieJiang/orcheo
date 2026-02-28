from __future__ import annotations
from uuid import UUID
from fastapi.testclient import TestClient
from orcheo.models import CredentialScope
from orcheo.vault import InMemoryCredentialVault


def _create_workflow(api_client: TestClient) -> str:
    response = api_client.post(
        "/api/workflows",
        json={"name": "Node Flow", "actor": "tester"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_node_execution_with_set_variable_node(api_client: TestClient) -> None:
    """Test executing a SetVariableNode in isolation."""
    response = api_client.post(
        "/api/nodes/execute",
        json={
            "node_config": {
                "type": "SetVariableNode",
                "name": "test_node",
                "variables": {"foo": "bar", "count": 42},
            },
            "inputs": {},
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"
    assert result["result"] == {"foo": "bar", "count": 42}
    assert result["error"] is None


def test_node_execution_with_delay_node(api_client: TestClient) -> None:
    """Test executing a DelayNode in isolation."""
    response = api_client.post(
        "/api/nodes/execute",
        json={
            "node_config": {
                "type": "DelayNode",
                "name": "delay_test",
                "duration_seconds": 0.01,
            },
            "inputs": {},
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"
    assert result["result"] == {"duration_seconds": 0.01}
    assert result["error"] is None


def test_node_execution_resolves_credentials(api_client: TestClient) -> None:
    """Placeholders in node config should resolve through the vault."""

    workflow_id = UUID(_create_workflow(api_client))
    vault: InMemoryCredentialVault = api_client.app.state.vault  # type: ignore[attr-defined]
    vault.create_credential(
        name="telegram_bot",
        provider="telegram",
        scopes=["bot"],
        secret="resolved-token",
        actor="tester",
        scope=CredentialScope.for_workflows(workflow_id),
    )

    response = api_client.post(
        "/api/nodes/execute",
        json={
            "node_config": {
                "type": "SetVariableNode",
                "name": "store_secret",
                "variables": {"token": "[[telegram_bot]]"},
            },
            "inputs": {},
            "workflow_id": str(workflow_id),
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"
    assert result["result"] == {"token": "resolved-token"}


def test_node_execution_with_inputs(api_client: TestClient) -> None:
    """Test executing a node with custom inputs."""
    response = api_client.post(
        "/api/nodes/execute",
        json={
            "node_config": {
                "type": "SetVariableNode",
                "name": "input_test",
                "variables": {"output": "processed"},
            },
            "inputs": {"input_value": "test_data"},
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"
    assert result["result"]["output"] == "processed"


def test_node_execution_missing_type(api_client: TestClient) -> None:
    """Test that missing node type returns 400 error."""
    response = api_client.post(
        "/api/nodes/execute",
        json={
            "node_config": {
                "name": "missing_type",
            },
            "inputs": {},
        },
    )

    assert response.status_code == 400
    result = response.json()
    assert "type" in result["detail"]


def test_node_execution_unknown_type(api_client: TestClient) -> None:
    """Test that unknown node type returns 400 error."""
    response = api_client.post(
        "/api/nodes/execute",
        json={
            "node_config": {
                "type": "NonExistentNode",
                "name": "unknown",
            },
            "inputs": {},
        },
    )

    assert response.status_code == 400
    result = response.json()
    assert "Unknown node type" in result["detail"]


def test_node_execution_invalid_config(api_client: TestClient) -> None:
    """Test that invalid node configuration returns error status."""
    response = api_client.post(
        "/api/nodes/execute",
        json={
            "node_config": {
                "type": "DelayNode",
                # Missing required 'name' field
                "duration_seconds": 1,
            },
            "inputs": {},
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "error"
    assert result["error"] is not None
    assert result["result"] is None


def test_node_execution_with_workflow_context(api_client: TestClient) -> None:
    """Test executing a node with workflow_id for credential context."""
    workflow_id = _create_workflow(api_client)

    response = api_client.post(
        "/api/nodes/execute",
        json={
            "node_config": {
                "type": "SetVariableNode",
                "name": "context_test",
                "variables": {"status": "executed"},
            },
            "inputs": {},
            "workflow_id": workflow_id,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"
    assert result["result"]["status"] == "executed"
