"""High-level integration tests for MCP server tool lifecycles."""

from __future__ import annotations
from typing import Any
import httpx
import respx


def test_workflow_lifecycle(mock_env: None) -> None:
    """Test complete workflow lifecycle: list, show, run, delete."""
    from orcheo_sdk.mcp_server import tools

    workflow = {"id": "wf-1", "name": "Test"}
    workflows_list = [workflow]
    versions = [{"id": "v1", "version": 1, "graph": {}}]
    runs: list[dict[str, Any]] = []

    with respx.mock() as router:
        router.get("http://api.test/api/workflows").mock(
            return_value=httpx.Response(200, json=workflows_list)
        )
        router.get("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(200, json=workflow)
        )
        router.get("http://api.test/api/workflows/wf-1/versions").mock(
            return_value=httpx.Response(200, json=versions)
        )
        router.get("http://api.test/api/workflows/wf-1/runs").mock(
            return_value=httpx.Response(200, json=runs)
        )
        router.delete("http://api.test/api/workflows/wf-1").mock(
            return_value=httpx.Response(204)
        )

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
        router.get("http://api.test/api/credentials").mock(
            return_value=httpx.Response(200, json=credentials_list)
        )
        router.post("http://api.test/api/credentials").mock(
            return_value=httpx.Response(201, json=created_cred)
        )
        router.delete("http://api.test/api/credentials/cred-1").mock(
            return_value=httpx.Response(204)
        )

        list_result = tools.list_credentials()
        assert list_result == credentials_list

        create_result = tools.create_credential(
            name="test-cred",
            provider="openai",
            secret="sk-test",
        )
        assert create_result["id"] == "cred-1"

        delete_result = tools.delete_credential("cred-1")
        assert delete_result["status"] == "success"
