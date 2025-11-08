import json
from typing import Any
from unittest.mock import Mock, patch
import httpx
import respx


def test_mcp_list_workflows(mock_env: None) -> None:
    """Test list_workflows MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

    payload = [
        {"id": "wf-1", "name": "Test Workflow", "slug": "test", "is_archived": False, "is_public": True}
    ]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = main_module.list_workflows.fn()

    assert result[0]["share_url"] == "http://canvas.test/chat/wf-1"
    assert result[0]["name"] == "Test Workflow"


def test_mcp_show_workflow(mock_env: None) -> None:
    """Test show_workflow MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

    workflow = {"id": "wf-1", "name": "Test", "is_public": True}
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

    assert result["workflow"]["share_url"] == "http://canvas.test/chat/wf-1"


def test_mcp_publish_workflow(mock_env: None) -> None:
    """Test publishing via MCP tool."""
    import orcheo_sdk.mcp_server.main as main_module

    payload = {
        "workflow": {"id": "wf-5", "name": "Demo", "is_public": True},
        "publish_token": "abc",
    }

    with respx.mock() as router:
        router.post("http://api.test/api/workflows/wf-5/publish").mock(
            return_value=httpx.Response(201, json=payload)
        )
        result = main_module.publish_workflow.fn("wf-5")

    assert result["share_url"] == "http://canvas.test/chat/wf-5"
    assert result["publish_token"] == "abc"


def test_mcp_rotate_publish_token(mock_env: None) -> None:
    """Test rotating publish token via MCP tool."""
    import orcheo_sdk.mcp_server.main as main_module

    payload = {
        "workflow": {"id": "wf-6", "name": "Demo", "is_public": True},
        "publish_token": "rot-123",
    }

    with respx.mock() as router:
        router.post("http://api.test/api/workflows/wf-6/publish/rotate").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = main_module.rotate_publish_token.fn("wf-6")

    assert result["workflow"]["share_url"] == "http://canvas.test/chat/wf-6"
    assert result["publish_token"] == "rot-123"


def test_mcp_unpublish_workflow(mock_env: None) -> None:
    """Test unpublishing via MCP tool."""
    import orcheo_sdk.mcp_server.main as main_module

    payload = {"id": "wf-7", "name": "Demo", "is_public": False}

    with respx.mock() as router:
        router.post("http://api.test/api/workflows/wf-7/publish/revoke").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = main_module.unpublish_workflow.fn("wf-7")

    assert result["workflow"]["share_url"] is None


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
