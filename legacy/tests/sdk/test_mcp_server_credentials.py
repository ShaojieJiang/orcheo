"""Tests for credential operations exposed by the MCP server."""

from __future__ import annotations
from typing import Any
import httpx
import respx


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


def test_mcp_list_credentials(mock_env: None) -> None:
    """Test list_credentials MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

    payload = [
        {
            "id": "cred-1",
            "name": "test-cred",
            "provider": "openai",
            "status": "active",
        }
    ]

    with respx.mock() as router:
        router.get("http://api.test/api/credentials").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = main_module.list_credentials.fn()

    assert result == payload


def test_mcp_create_credential(mock_env: None) -> None:
    """Test create_credential MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

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
        result = main_module.create_credential.fn(
            name="test-cred",
            provider="openai",
            secret="sk-test",
        )

    assert result["id"] == "cred-1"


def test_mcp_delete_credential(mock_env: None) -> None:
    """Test delete_credential MCP tool wrapper to cover return statement."""
    import orcheo_sdk.mcp_server.main as main_module

    with respx.mock() as router:
        router.delete("http://api.test/api/credentials/cred-1").mock(
            return_value=httpx.Response(204)
        )
        result = main_module.delete_credential.fn("cred-1")

    assert result["status"] == "success"
