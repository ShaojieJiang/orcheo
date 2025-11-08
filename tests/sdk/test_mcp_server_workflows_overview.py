"""Tests for listing and inspecting workflows via the MCP server."""

from __future__ import annotations
import httpx
import respx


def test_list_workflows_with_profile(mock_env: None) -> None:
    """Test listing workflows with explicit profile parameter."""
    from orcheo_sdk.mcp_server import tools

    payload = [
        {
            "id": "wf-1",
            "name": "Test Workflow",
            "slug": "test",
            "is_archived": False,
            "is_public": True,
            "require_login": False,
        }
    ]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = tools.list_workflows(archived=False, profile=None)

    assert result[0]["id"] == "wf-1"
    assert result[0]["publish_summary"]["status"] == "public"
    assert result[0]["publish_summary"]["share_url"] == "http://api.test/chat/wf-1"


def test_list_workflows_success(mock_env: None) -> None:
    """Test listing workflows."""
    from orcheo_sdk.mcp_server import tools

    payload = [
        {
            "id": "wf-1",
            "name": "Test Workflow",
            "slug": "test",
            "is_archived": False,
            "is_public": False,
        }
    ]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = tools.list_workflows()

    assert result[0]["publish_summary"]["status"] == "private"


def test_list_workflows_with_archived(mock_env: None) -> None:
    """Test listing workflows including archived ones."""
    from orcheo_sdk.mcp_server import tools

    payload = [
        {
            "id": "wf-1",
            "name": "Active",
            "slug": "active",
            "is_archived": False,
            "is_public": False,
        },
        {
            "id": "wf-2",
            "name": "Archived",
            "slug": "archived",
            "is_archived": True,
            "is_public": True,
            "require_login": True,
        },
    ]

    with respx.mock() as router:
        router.get("http://api.test/api/workflows?include_archived=true").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = tools.list_workflows(archived=True)

    assert len(result) == 2
    assert result[1]["publish_summary"]["require_login"] is True


def test_show_workflow_success(mock_env: None) -> None:
    """Test showing workflow details."""
    from orcheo_sdk.mcp_server import tools

    workflow = {
        "id": "wf-1",
        "name": "Test",
        "is_public": True,
        "require_login": False,
    }
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

    assert result["workflow"]["id"] == "wf-1"
    assert result["workflow"]["publish_summary"]["status"] == "public"
    assert result["latest_version"] == versions[0]
    assert len(result["recent_runs"]) == 1


def test_show_workflow_with_cached_runs(mock_env: None) -> None:
    """Test show_workflow_data with pre-fetched runs."""
    from orcheo_sdk.mcp_server.config import get_api_client
    from orcheo_sdk.services.workflows import show_workflow_data

    client, _ = get_api_client()
    workflow = {
        "id": "wf-1",
        "name": "Test",
        "is_public": False,
    }
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
        )

    assert result["workflow"]["publish_summary"]["status"] == "private"
    assert result["latest_version"] == versions[0]
    assert len(result["recent_runs"]) == 1


def test_show_workflow_with_runs_none_path(mock_env: None) -> None:
    """Test show_workflow_data when runs is None and include_runs is True."""
    from orcheo_sdk.mcp_server.config import get_api_client
    from orcheo_sdk.services.workflows import show_workflow_data

    client, _ = get_api_client()
    workflow = {
        "id": "wf-1",
        "name": "Test",
        "is_public": False,
    }
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
        )

    assert result["workflow"]["publish_summary"]["status"] == "private"
    assert result["latest_version"] == versions[0]
    assert len(result["recent_runs"]) == 1


def test_show_workflow_without_runs(mock_env: None) -> None:
    """Test show_workflow_data when include_runs is False."""
    from orcheo_sdk.mcp_server.config import get_api_client
    from orcheo_sdk.services.workflows import show_workflow_data

    client, _ = get_api_client()
    workflow = {
        "id": "wf-1",
        "name": "Test",
        "is_public": False,
    }
    versions = [{"id": "v1", "version": 1, "graph": {}}]

    with respx.mock():
        result = show_workflow_data(
            client,
            "wf-1",
            include_runs=False,
            workflow=workflow,
            versions=versions,
        )

    assert result["workflow"]["publish_summary"]["status"] == "private"
    assert result["latest_version"] == versions[0]
    assert result["recent_runs"] == []


def test_publish_workflow_tool(mock_env: None) -> None:
    """Test the publish workflow MCP tool helper."""
    from orcheo_sdk.mcp_server import tools

    response = {
        "workflow": {
            "id": "wf-1",
            "name": "Demo",
            "is_public": True,
            "require_login": True,
        },
        "publish_token": "pk-test",
        "message": "Store securely",
    }

    with respx.mock() as router:
        router.post("http://api.test/api/workflows/wf-1/publish").mock(
            return_value=httpx.Response(201, json=response)
        )
        result = tools.publish_workflow("wf-1", require_login=True)

    assert result["publish_summary"]["status"] == "public"
    assert result["publish_token"] == "pk-test"


def test_rotate_publish_token_tool(mock_env: None) -> None:
    """Test rotating publish token via MCP tool helper."""
    from orcheo_sdk.mcp_server import tools

    response = {
        "workflow": {
            "id": "wf-1",
            "name": "Demo",
            "is_public": True,
            "publish_token_rotated_at": "2024-02-02T00:00:00Z",
        },
        "publish_token": "pk-rotated",
    }

    with respx.mock() as router:
        router.post("http://api.test/api/workflows/wf-1/publish/rotate").mock(
            return_value=httpx.Response(200, json=response)
        )
        result = tools.rotate_publish_token("wf-1")

    assert result["publish_token"] == "pk-rotated"
    assert result["publish_summary"]["status"] == "public"


def test_unpublish_workflow_tool(mock_env: None) -> None:
    """Test unpublishing a workflow via MCP tool helper."""
    from orcheo_sdk.mcp_server import tools

    response = {
        "id": "wf-1",
        "name": "Demo",
        "is_public": False,
        "require_login": False,
    }

    with respx.mock() as router:
        router.post("http://api.test/api/workflows/wf-1/publish/revoke").mock(
            return_value=httpx.Response(200, json=response)
        )
        result = tools.unpublish_workflow("wf-1")

    assert result["publish_summary"]["status"] == "private"
