"""Tests for listing and inspecting workflows via the MCP server."""

from __future__ import annotations
import httpx
import respx


def test_list_workflows_with_profile(mock_env: None) -> None:
    """Test listing workflows with explicit profile parameter."""
    from orcheo_sdk.mcp_server import tools

    payload = [
        {"id": "wf-1", "name": "Test Workflow", "slug": "test", "is_archived": False, "is_public": True}
    ]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = tools.list_workflows(archived=False, profile=None)

    assert result[0]["share_url"] == "http://canvas.test/chat/wf-1"


def test_list_workflows_success(mock_env: None) -> None:
    """Test listing workflows."""
    from orcheo_sdk.mcp_server import tools

    payload = [
        {"id": "wf-1", "name": "Test Workflow", "slug": "test", "is_archived": False, "is_public": True}
    ]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = tools.list_workflows()

    assert result[0]["share_url"] == "http://canvas.test/chat/wf-1"


def test_list_workflows_with_archived(mock_env: None) -> None:
    """Test listing workflows including archived ones."""
    from orcheo_sdk.mcp_server import tools

    payload = [
        {"id": "wf-1", "name": "Active", "slug": "active", "is_archived": False, "is_public": True},
        {"id": "wf-2", "name": "Archived", "slug": "archived", "is_archived": True, "is_public": False},
    ]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows?include_archived=true").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = tools.list_workflows(archived=True)

    assert len(result) == 2
    assert result[0]["share_url"] == "http://canvas.test/chat/wf-1"
    assert result[1]["share_url"] is None


def test_show_workflow_success(mock_env: None) -> None:
    """Test showing workflow details."""
    from orcheo_sdk.mcp_server import tools

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

        result = tools.show_workflow("wf-1")

    assert result["workflow"]["share_url"] == "http://canvas.test/chat/wf-1"
    assert result["latest_version"] == versions[0]
    assert len(result["recent_runs"]) == 1


def test_show_workflow_with_cached_runs(mock_env: None) -> None:
    """Test show_workflow_data with pre-fetched runs."""
    from orcheo_sdk.mcp_server.config import get_api_client
    from orcheo_sdk.services.workflows import show_workflow_data

    client, settings = get_api_client()
    workflow = {"id": "wf-1", "name": "Test", "is_public": True}
    versions = [{"id": "v1", "version": 1, "graph": {}}]
    runs = [{"id": "r1", "status": "completed", "created_at": "2025-01-01T00:00:00Z"}]

    with respx.mock():
        result = show_workflow_data(
            client,
            "wf-1",
            include_runs=True,
            workflow=workflow,
            versions=versions,
            runs=runs,
            canvas_base_url=settings.canvas_base_url,
        )

    assert result["workflow"]["share_url"] == "http://canvas.test/chat/wf-1"
    assert result["latest_version"] == versions[0]
    assert len(result["recent_runs"]) == 1


def test_show_workflow_with_runs_none_path(mock_env: None) -> None:
    """Test show_workflow_data when runs is None and include_runs is True."""
    from orcheo_sdk.mcp_server.config import get_api_client
    from orcheo_sdk.services.workflows import show_workflow_data

    client, settings = get_api_client()
    workflow = {"id": "wf-1", "name": "Test", "is_public": True}
    versions = [{"id": "v1", "version": 1, "graph": {}}]
    runs = [{"id": "r1", "status": "completed", "created_at": "2025-01-01T00:00:00Z"}]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(200, json=runs)
        )

        result = show_workflow_data(
            client,
            "wf-1",
            include_runs=True,
            workflow=workflow,
            versions=versions,
            runs=None,
            canvas_base_url=settings.canvas_base_url,
        )

    assert result["workflow"]["share_url"] == "http://canvas.test/chat/wf-1"
    assert result["latest_version"] == versions[0]
    assert len(result["recent_runs"]) == 1


def test_show_workflow_without_runs(mock_env: None) -> None:
    """Test show_workflow_data when include_runs is False."""
    from orcheo_sdk.mcp_server.config import get_api_client
    from orcheo_sdk.services.workflows import show_workflow_data

    client, settings = get_api_client()
    workflow = {"id": "wf-1", "name": "Test", "is_public": True}
    versions = [{"id": "v1", "version": 1, "graph": {}}]

    with respx.mock():
        result = show_workflow_data(
            client,
            "wf-1",
            include_runs=False,
            workflow=workflow,
            versions=versions,
            canvas_base_url=settings.canvas_base_url,
        )

    assert result["workflow"]["share_url"] == "http://canvas.test/chat/wf-1"
    assert result["latest_version"] == versions[0]
    assert result["recent_runs"] == []
