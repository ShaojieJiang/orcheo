"""Tests for the Orcheo MCP server."""

from __future__ import annotations
from typing import Any
from unittest.mock import Mock, patch
import httpx
import pytest
import respx
from orcheo_sdk.cli.errors import CLIError


@pytest.fixture()
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up mock environment variables."""
    monkeypatch.setenv("ORCHEO_API_URL", "http://api.test")
    monkeypatch.setenv("ORCHEO_SERVICE_TOKEN", "test-token")


# ==============================================================================
# Configuration Tests
# ==============================================================================


def test_get_api_client_with_env_vars(mock_env: None) -> None:
    """Test API client configuration from environment variables."""
    from orcheo_sdk.mcp_server.config import get_api_client

    client, settings = get_api_client()
    assert client.base_url == "http://api.test"
    assert settings.api_url == "http://api.test"
    assert settings.service_token == "test-token"


def test_get_api_client_missing_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test API client with default URL when env var is missing."""
    from orcheo_sdk.mcp_server.config import get_api_client

    monkeypatch.delenv("ORCHEO_API_URL", raising=False)
    monkeypatch.setenv("ORCHEO_SERVICE_TOKEN", "test-token")

    # Should use default URL from CLI config
    client, settings = get_api_client()
    assert client is not None
    assert settings is not None


def test_create_server() -> None:
    """Test MCP server creation."""
    from orcheo_sdk.mcp_server.main import create_server

    server = create_server()
    assert server is not None
    assert server.name == "Orcheo CLI"


# ==============================================================================
# Workflow Tools Tests
# ==============================================================================


def test_list_workflows_success(mock_env: None) -> None:
    """Test listing workflows."""
    from orcheo_sdk.mcp_server import tools

    payload = [
        {"id": "wf-1", "name": "Test Workflow", "slug": "test", "is_archived": False}
    ]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = tools.list_workflows()

    assert result == payload


def test_list_workflows_with_archived(mock_env: None) -> None:
    """Test listing workflows including archived ones."""
    from orcheo_sdk.mcp_server import tools

    payload = [
        {"id": "wf-1", "name": "Active", "slug": "active", "is_archived": False},
        {"id": "wf-2", "name": "Archived", "slug": "archived", "is_archived": True},
    ]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows?include_archived=true").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = tools.list_workflows(archived=True)

    assert len(result) == 2


def test_show_workflow_success(mock_env: None) -> None:
    """Test showing workflow details."""
    from orcheo_sdk.mcp_server import tools

    workflow = {"id": "wf-1", "name": "Test"}
    versions = [{"id": "v1", "version": 1, "graph": {}}]
    runs = [{"id": "r1", "status": "completed", "created_at": "2025-01-01T00:00:00Z"}]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        router.get("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(200, json=runs)
        )

        result = tools.show_workflow("wf-1")

    assert result["workflow"] == workflow
    assert result["latest_version"] == versions[0]
    assert len(result["recent_runs"]) == 1


def test_run_workflow_success(mock_env: None) -> None:
    """Test running a workflow."""
    from orcheo_sdk.mcp_server import tools

    versions = [{"id": "v1", "version": 1, "graph": {}}]
    run_result = {"id": "run-1", "status": "pending"}

    with respx.mock() as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        # Mock the executor (imported from orcheo_sdk.client)
        with patch("orcheo_sdk.client.HttpWorkflowExecutor") as mock_exec:
            mock_executor = Mock()
            mock_executor.trigger_run.return_value = run_result
            mock_exec.return_value = mock_executor

            result = tools.run_workflow("wf-1", inputs={"test": "value"})

    assert result == run_result


def test_run_workflow_no_versions(mock_env: None) -> None:
    """Test running workflow fails when no versions exist."""
    from orcheo_sdk.mcp_server import tools

    with respx.mock() as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=[])
        )

        with pytest.raises(CLIError, match="no versions"):
            tools.run_workflow("wf-1")


def test_delete_workflow_success(mock_env: None) -> None:
    """Test deleting a workflow."""
    from orcheo_sdk.mcp_server import tools

    with respx.mock() as router:
        router.delete("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(204)
        )
        result = tools.delete_workflow("wf-1")

    assert result["status"] == "success"
    assert "wf-1" in result["message"]


def test_download_workflow_json(mock_env: None) -> None:
    """Test downloading workflow as JSON."""
    from orcheo_sdk.mcp_server import tools

    workflow = {"id": "wf-1", "name": "Test", "metadata": {}}
    versions = [{"id": "v1", "version": 1, "graph": {"nodes": [], "edges": []}}]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )

        result = tools.download_workflow("wf-1", format_type="json")

    assert result["format"] == "json"
    assert "content" in result
    assert "Test" in result["content"]


def test_download_workflow_no_versions(mock_env: None) -> None:
    """Test downloading workflow fails when no versions exist."""
    from orcheo_sdk.mcp_server import tools

    workflow = {"id": "wf-1", "name": "Test"}

    with respx.mock() as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=[])
        )

        with pytest.raises(CLIError, match="no versions"):
            tools.download_workflow("wf-1")


# ==============================================================================
# Node Tools Tests
# ==============================================================================


def test_list_nodes(mock_env: None) -> None:
    """Test listing nodes."""
    from orcheo_sdk.mcp_server import tools

    result = tools.list_nodes()
    assert isinstance(result, list)
    assert len(result) > 0
    # Check that known nodes are present
    node_names = [node["name"] for node in result]
    assert "WebhookTriggerNode" in node_names


def test_list_nodes_with_tag_filter(mock_env: None) -> None:
    """Test listing nodes with tag filter."""
    from orcheo_sdk.mcp_server import tools

    result = tools.list_nodes(tag="trigger")
    assert isinstance(result, list)
    # All results should match the filter
    for node in result:
        assert (
            "trigger" in node["name"].lower() or "trigger" in node["category"].lower()
        )


def test_show_node_success(mock_env: None) -> None:
    """Test showing node details."""
    from orcheo_sdk.mcp_server import tools

    result = tools.show_node("WebhookTriggerNode")
    assert result["name"] == "WebhookTriggerNode"
    assert "category" in result
    assert "description" in result
    assert "schema" in result


def test_show_node_not_found(mock_env: None) -> None:
    """Test showing non-existent node."""
    from orcheo_sdk.mcp_server import tools

    with pytest.raises(CLIError, match="not registered"):
        tools.show_node("NonExistentNode")


# ==============================================================================
# Credential Tools Tests
# ==============================================================================


def test_list_credentials_success(mock_env: None) -> None:
    """Test listing credentials."""
    from orcheo_sdk.mcp_server import tools

    payload = [
        {
            "id": "cred-1",
            "name": "test-cred",
            "provider": "openai",
            "status": "active",
            "access": "private",
        }
    ]

    with respx.mock() as router:
        router.get("http://api.test/api/credentials").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = tools.list_credentials()

    assert result == payload


def test_list_credentials_with_workflow_filter(mock_env: None) -> None:
    """Test listing credentials filtered by workflow."""
    from orcheo_sdk.mcp_server import tools

    payload: list[dict[str, Any]] = []

    with respx.mock() as router:
        router.get("http://api.test/api/credentials?workflow_id=wf-1").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = tools.list_credentials(workflow_id="wf-1")

    assert result == payload


def test_create_credential_success(mock_env: None) -> None:
    """Test creating a credential."""
    from orcheo_sdk.mcp_server import tools

    response = {
        "id": "cred-1",
        "name": "test-cred",
        "provider": "openai",
        "status": "active",
    }

    with respx.mock() as router:
        router.post("http://api.test/api/credentials").mock(
            return_value=httpx.Response(201, json=response)
        )
        result = tools.create_credential(
            name="test-cred",
            provider="openai",
            secret="sk-test",
        )

    assert result["id"] == "cred-1"


def test_delete_credential_success(mock_env: None) -> None:
    """Test deleting a credential."""
    from orcheo_sdk.mcp_server import tools

    with respx.mock() as router:
        router.delete("http://api.test/api/credentials/cred-1").mock(
            return_value=httpx.Response(204)
        )
        result = tools.delete_credential("cred-1")

    assert result["status"] == "success"


def test_get_credential_reference() -> None:
    """Test getting credential reference string."""
    from orcheo_sdk.mcp_server import tools

    result = tools.get_credential_reference("my-cred")
    assert result["reference"] == "[[my-cred]]"
    assert "usage" in result


# ==============================================================================
# Code Generation Tools Tests
# ==============================================================================


def test_generate_workflow_scaffold_success(mock_env: None) -> None:
    """Test generating workflow scaffold."""
    from orcheo_sdk.mcp_server import tools

    workflow = {"id": "wf-1", "name": "Test"}
    versions = [{"id": "v1", "version": 1}]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )

        result = tools.generate_workflow_scaffold("wf-1")

    assert "code" in result
    assert "workflow" in result
    assert "wf-1" in result["code"]
    assert "HttpWorkflowExecutor" in result["code"]


def test_generate_workflow_scaffold_no_versions(mock_env: None) -> None:
    """Test scaffold generation fails when no versions exist."""
    from orcheo_sdk.mcp_server import tools

    workflow = {"id": "wf-1", "name": "Test"}

    with respx.mock() as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=[])
        )

        with pytest.raises(CLIError, match="no versions"):
            tools.generate_workflow_scaffold("wf-1")


def test_generate_workflow_template() -> None:
    """Test generating workflow template."""
    from orcheo_sdk.mcp_server import tools

    result = tools.generate_workflow_template()
    assert "code" in result
    assert "description" in result
    assert "LangGraph" in result["code"]
    assert "StateGraph" in result["code"]
    assert "SetVariableNode" in result["code"]


# ==============================================================================
# Agent Tool Discovery Tests
# ==============================================================================


def test_list_agent_tools(mock_env: None) -> None:
    """Test listing agent tools."""
    from orcheo_sdk.mcp_server import tools

    result = tools.list_agent_tools()
    assert isinstance(result, list)
    # Result may be empty if no tools are registered
    if result:
        assert "name" in result[0]
        assert "category" in result[0]


def test_list_agent_tools_with_category_filter(mock_env: None) -> None:
    """Test listing agent tools with category filter."""
    from orcheo_sdk.mcp_server import tools

    result = tools.list_agent_tools(category="test")
    assert isinstance(result, list)
    # All results should match the filter if any exist
    for tool in result:
        assert "test" in tool["name"].lower() or "test" in tool["category"].lower()


def test_show_agent_tool_not_found(mock_env: None) -> None:
    """Test showing non-existent agent tool."""
    from orcheo_sdk.mcp_server import tools

    with pytest.raises(CLIError, match="not registered"):
        tools.show_agent_tool("NonExistentTool")


# ==============================================================================
# Integration Tests
# ==============================================================================


def test_workflow_lifecycle(mock_env: None) -> None:
    """Test complete workflow lifecycle: list, show, run, delete."""
    from orcheo_sdk.mcp_server import tools

    workflow = {"id": "wf-1", "name": "Test"}
    workflows_list = [workflow]
    versions = [{"id": "v1", "version": 1, "graph": {}}]
    runs: list[dict[str, Any]] = []

    with respx.mock() as router:
        # List workflows
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=workflows_list)
        )

        # Show workflow
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        router.get("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(200, json=runs)
        )

        # Delete workflow
        router.delete("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(204)
        )

        # Execute lifecycle
        list_result = tools.list_workflows()
        assert len(list_result) == 1

        show_result = tools.show_workflow("wf-1")
        assert show_result["workflow"]["id"] == "wf-1"

        delete_result = tools.delete_workflow("wf-1")
        assert delete_result["status"] == "success"


def test_credential_lifecycle(mock_env: None) -> None:
    """Test complete credential lifecycle: list, create, delete."""
    from orcheo_sdk.mcp_server import tools

    credentials_list: list[dict[str, Any]] = []
    created_cred = {
        "id": "cred-1",
        "name": "test-cred",
        "provider": "openai",
        "status": "active",
    }

    with respx.mock() as router:
        # List credentials (empty)
        router.get("http://api.test/api/credentials").mock(
            return_value=httpx.Response(200, json=credentials_list)
        )

        # Create credential
        router.post("http://api.test/api/credentials").mock(
            return_value=httpx.Response(201, json=created_cred)
        )

        # Delete credential
        router.delete("http://api.test/api/credentials/cred-1").mock(
            return_value=httpx.Response(204)
        )

        # Execute lifecycle
        list_result = tools.list_credentials()
        assert len(list_result) == 0

        create_result = tools.create_credential(
            name="test-cred",
            provider="openai",
            secret="sk-test",
        )
        assert create_result["id"] == "cred-1"

        delete_result = tools.delete_credential("cred-1")
        assert delete_result["status"] == "success"
