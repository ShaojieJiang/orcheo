"""Tests for service token management via the MCP server."""

from __future__ import annotations
import httpx
import respx


def test_list_service_tokens_success(mock_env: None) -> None:
    """Test listing service tokens."""
    from orcheo_sdk.mcp_server import tools

    payload = {
        "tokens": [
            {
                "identifier": "token-1",
                "scopes": ["read", "write"],
                "workspace_ids": ["ws-1"],
                "issued_at": "2025-01-01T00:00:00Z",
            }
        ],
        "total": 1,
    }

    with respx.mock() as router:
        router.get("http://api.test/api/admin/service-tokens").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = tools.list_service_tokens()

    assert result == payload
    assert result["total"] == 1


def test_show_service_token_success(mock_env: None) -> None:
    """Test showing service token details."""
    from orcheo_sdk.mcp_server import tools

    token = {
        "identifier": "token-1",
        "scopes": ["read"],
        "workspace_ids": ["ws-1"],
        "issued_at": "2025-01-01T00:00:00Z",
    }

    with respx.mock() as router:
        router.get("http://api.test/api/admin/service-tokens/token-1").mock(
            return_value=httpx.Response(200, json=token)
        )
        result = tools.show_service_token("token-1")

    assert result == token


def test_create_service_token_success(mock_env: None) -> None:
    """Test creating a service token."""
    from orcheo_sdk.mcp_server import tools

    response = {
        "identifier": "token-1",
        "secret": "secret-value",
        "scopes": ["read"],
        "workspace_ids": ["ws-1"],
    }

    with respx.mock() as router:
        router.post("http://api.test/api/admin/service-tokens").mock(
            return_value=httpx.Response(201, json=response)
        )
        result = tools.create_service_token(
            identifier="token-1",
            scopes=["read"],
            workspace_ids=["ws-1"],
        )

    assert result["identifier"] == "token-1"
    assert result["secret"] == "secret-value"


def test_rotate_service_token_success(mock_env: None) -> None:
    """Test rotating a service token."""
    from orcheo_sdk.mcp_server import tools

    response = {
        "identifier": "token-2",
        "secret": "new-secret-value",
        "message": "Token rotated successfully",
    }

    with respx.mock() as router:
        router.post("http://api.test/api/admin/service-tokens/token-1/rotate").mock(
            return_value=httpx.Response(200, json=response)
        )
        result = tools.rotate_service_token("token-1")

    assert result["identifier"] == "token-2"
    assert result["secret"] == "new-secret-value"


def test_revoke_service_token_success(mock_env: None) -> None:
    """Test revoking a service token."""
    from orcheo_sdk.mcp_server import tools

    with respx.mock() as router:
        router.delete("http://api.test/api/admin/service-tokens/token-1").mock(
            return_value=httpx.Response(204)
        )
        result = tools.revoke_service_token("token-1", "Security breach")

    assert result["status"] == "success"


def test_mcp_list_service_tokens(mock_env: None) -> None:
    """Test list_service_tokens MCP tool wrapper."""
    import orcheo_sdk.mcp_server.main as main_module

    payload = {
        "tokens": [{"identifier": "token-1"}],
        "total": 1,
    }

    with respx.mock() as router:
        router.get("http://api.test/api/admin/service-tokens").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = main_module.list_service_tokens.fn()

    assert result == payload


def test_mcp_show_service_token(mock_env: None) -> None:
    """Test show_service_token MCP tool wrapper."""
    import orcheo_sdk.mcp_server.main as main_module

    token = {"identifier": "token-1"}

    with respx.mock() as router:
        router.get("http://api.test/api/admin/service-tokens/token-1").mock(
            return_value=httpx.Response(200, json=token)
        )
        result = main_module.show_service_token.fn("token-1")

    assert result == token


def test_mcp_create_service_token(mock_env: None) -> None:
    """Test create_service_token MCP tool wrapper."""
    import orcheo_sdk.mcp_server.main as main_module

    response = {"identifier": "token-1", "secret": "secret-value"}

    with respx.mock() as router:
        router.post("http://api.test/api/admin/service-tokens").mock(
            return_value=httpx.Response(201, json=response)
        )
        result = main_module.create_service_token.fn()

    assert result["identifier"] == "token-1"


def test_mcp_rotate_service_token(mock_env: None) -> None:
    """Test rotate_service_token MCP tool wrapper."""
    import orcheo_sdk.mcp_server.main as main_module

    response = {"identifier": "token-2", "secret": "new-secret"}

    with respx.mock() as router:
        router.post("http://api.test/api/admin/service-tokens/token-1/rotate").mock(
            return_value=httpx.Response(200, json=response)
        )
        result = main_module.rotate_service_token.fn("token-1")

    assert result["identifier"] == "token-2"


def test_mcp_revoke_service_token(mock_env: None) -> None:
    """Test revoke_service_token MCP tool wrapper."""
    import orcheo_sdk.mcp_server.main as main_module

    with respx.mock() as router:
        router.delete("http://api.test/api/admin/service-tokens/token-1").mock(
            return_value=httpx.Response(204)
        )
        result = main_module.revoke_service_token.fn("token-1", "Test reason")

    assert result["status"] == "success"
