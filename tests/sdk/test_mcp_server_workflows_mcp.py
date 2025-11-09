"""Tests for MCP wrapper functions related to workflows."""

from __future__ import annotations
import json
from typing import Any
from unittest.mock import Mock, patch
import httpx
import respx


def test_mcp_list_workflows(mock_env: None) -> None:
    """Test list_workflows MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

    payload = [
        {
            "id": "wf-1",
            "name": "Test Workflow",
            "slug": "test",
            "is_archived": False,
            "is_public": True,
            "require_login": False,
            "published_at": "2024-01-01T00:00:00Z",
        }
    ]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = main_module.list_workflows.fn()

    assert result[0]["share_url"] == "http://api.test/chat/wf-1"


def test_mcp_show_workflow(mock_env: None) -> None:
    """Test show_workflow MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

    workflow = {"id": "wf-1", "name": "Test", "is_public": True, "require_login": False}
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

        result = main_module.show_workflow.fn("wf-1")

    assert result["workflow"]["share_url"] == "http://api.test/chat/wf-1"


def test_mcp_run_workflow(mock_env: None) -> None:
    """Test run_workflow MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

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

            result = main_module.run_workflow.fn("wf-1")

    assert result == run_result


def test_mcp_delete_workflow(mock_env: None) -> None:
    """Test delete_workflow MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

    with respx.mock() as router:
        router.delete("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(204)
        )
        result = main_module.delete_workflow.fn("wf-1")

    assert result["status"] == "success"


def test_mcp_upload_workflow(mock_env: None, tmp_path: Any) -> None:
    """Test upload_workflow MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

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

        result = main_module.upload_workflow.fn(str(json_file))

    assert result["id"] == "wf-1"


def test_mcp_download_workflow(mock_env: None) -> None:
    """Test download_workflow MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

    workflow = {"id": "wf-1", "name": "Test", "metadata": {}}
    versions = [{"id": "v1", "version": 1, "graph": {"nodes": [], "edges": []}}]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )

        result = main_module.download_workflow.fn("wf-1", format_type="json")

    assert "content" in result


def test_mcp_publish_workflow(mock_env: None) -> None:
    import orcheo_sdk.mcp_server.main as main_module

    payload = {
        "workflow": {
            "id": "wf-1",
            "is_public": True,
            "require_login": True,
            "published_at": "2024-01-01T00:00:00Z",
        },
        "message": "ok",
    }

    with respx.mock() as router:
        router.post("http://api.test/api/workflows/wf-1/publish").mock(
            return_value=httpx.Response(201, json=payload)
        )
        result = main_module.publish_workflow.fn("wf-1", require_login=True)

    assert result["workflow"]["share_url"] == "http://api.test/chat/wf-1"
    assert result["message"] == "ok"


def test_mcp_unpublish_workflow(mock_env: None) -> None:
    import orcheo_sdk.mcp_server.main as main_module

    workflow = {
        "id": "wf-1",
        "is_public": False,
        "require_login": False,
    }

    with respx.mock() as router:
        router.post("http://api.test/api/workflows/wf-1/publish/revoke").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        result = main_module.unpublish_workflow.fn("wf-1")

    assert result["workflow"]["is_public"] is False


def test_mcp_generate_workflow_scaffold(mock_env: None) -> None:
    """Test generate_workflow_scaffold MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

    workflow = {"id": "wf-1", "name": "Test"}
    versions = [{"id": "v1", "version": 1}]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )

        result = main_module.generate_workflow_scaffold.fn("wf-1")

    assert "code" in result


def test_mcp_generate_workflow_template() -> None:
    """Test generate_workflow_template MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

    result = main_module.generate_workflow_template.fn()
    assert "code" in result
