"""Tests for uploading workflows and generating helper artifacts."""

from __future__ import annotations
import json
from typing import Any
import httpx
import pytest
import respx
from orcheo_sdk.cli.errors import CLIError


def test_upload_workflow_fake_console_print(mock_env: None, tmp_path: Any) -> None:
    """Test that _FakeConsole.print is called in upload_workflow_data."""
    from orcheo_sdk.mcp_server.config import get_api_client
    from orcheo_sdk.services.workflows import upload_workflow_data

    client, _ = get_api_client()

    py_file = tmp_path / "workflow.py"
    py_file.write_text(
        """
from langgraph.graph import StateGraph, START, END
from orcheo.nodes import SetVariableNode

builder = StateGraph(dict)
builder.add_node("set_var", SetVariableNode(name="set_var", key="result", value="test"))
builder.add_edge(START, "set_var")
builder.add_edge("set_var", END)
graph = builder.compile()
"""
    )

    workflow_response = {
        "id": "wf-1",
        "name": "Test Workflow",
        "slug": "test-workflow",
        "metadata": {},
    }
    version_response = {"id": "v1", "version": 1, "workflow_id": "wf-1"}

    with respx.mock(assert_all_called=False) as router:
        router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=workflow_response)
        )
        router.post("http://api.test/api/workflows/wf-1/versions/ingest").mock(
            return_value=httpx.Response(201, json=version_response)
        )

        result = upload_workflow_data(
            client=client,
            file_path=str(py_file),
            workflow_name="Test Workflow",
            console=None,
        )

    assert result["id"] == "wf-1"


def test_upload_workflow_with_entrypoint(mock_env: None, tmp_path: Any) -> None:
    """Test uploading a LangGraph workflow with custom entrypoint."""
    from orcheo_sdk.mcp_server.config import get_api_client
    from orcheo_sdk.services.workflows import upload_workflow_data

    client, _ = get_api_client()

    py_file = tmp_path / "workflow.py"
    py_file.write_text(
        """
from langgraph.graph import StateGraph, START, END
from orcheo.nodes import SetVariableNode

builder = StateGraph(dict)
builder.add_node("set_var", SetVariableNode(name="set_var", key="result", value="test"))
builder.add_edge(START, "set_var")
builder.add_edge("set_var", END)
my_custom_graph = builder.compile()
"""
    )

    workflow_response = {
        "id": "wf-1",
        "name": "Test Workflow",
        "slug": "test-workflow",
        "metadata": {},
    }
    version_response = {"id": "v1", "version": 1, "workflow_id": "wf-1"}

    with respx.mock(assert_all_called=False) as router:
        router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=workflow_response)
        )
        router.post("http://api.test/api/workflows/wf-1/versions/ingest").mock(
            return_value=httpx.Response(201, json=version_response)
        )

        result = upload_workflow_data(
            client=client,
            file_path=str(py_file),
            workflow_name="Test Workflow",
            entrypoint="my_custom_graph",
            console=None,
        )

    assert result["id"] == "wf-1"


def test_upload_workflow_json_file(mock_env: None, tmp_path: Any) -> None:
    """Test uploading workflow from JSON file."""
    from orcheo_sdk.mcp_server import tools

    workflow_json = {
        "name": "Test Workflow",
        "graph": {"nodes": [], "edges": []},
    }
    json_file = tmp_path / "workflow.json"
    json_file.write_text(json.dumps(workflow_json))

    response = {"id": "wf-1", "name": "Test Workflow", "slug": "test-workflow"}

    with respx.mock() as router:
        router.post("http://api.test/api/workflows").mock(
            return_value=httpx.Response(201, json=response)
        )

        result = tools.upload_workflow(str(json_file))

    assert result["id"] == "wf-1"
    assert result["name"] == "Test Workflow"


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
