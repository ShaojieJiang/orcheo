"""Tests for executing and downloading workflows via the MCP server."""

from __future__ import annotations
from typing import Any
from unittest.mock import Mock, patch
import httpx
import pytest
import respx
from orcheo_sdk.cli.errors import CLIError


def test_run_workflow_success(mock_env: None) -> None:
    """Test running a workflow."""
    from orcheo_sdk.mcp_server import tools

    versions = [{"id": "v1", "version": 1, "graph": {}}]
    run_result = {"id": "run-1", "status": "pending"}

    with respx.mock() as router:
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
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


def test_download_workflow_to_file(mock_env: None, tmp_path: Any) -> None:
    """Test downloading workflow to a file."""
    from orcheo_sdk.mcp_server import tools

    workflow = {"id": "wf-1", "name": "Test", "metadata": {}}
    versions = [{"id": "v1", "version": 1, "graph": {"nodes": [], "edges": []}}]
    output_file = tmp_path / "workflow.json"

    with respx.mock() as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )

        result = tools.download_workflow(
            "wf-1", output_path=str(output_file), format_type="json"
        )

    assert result["status"] == "success"
    assert str(output_file) in result["message"]
    assert output_file.exists()
    assert "Test" in output_file.read_text()


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
