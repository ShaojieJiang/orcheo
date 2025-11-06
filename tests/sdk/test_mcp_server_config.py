"""Tests for MCP server configuration and entry points."""

from __future__ import annotations
from unittest.mock import patch
import pytest


def test_get_api_client_with_env_vars(mock_env: None) -> None:
    """Test API client configuration from environment variables."""
    from orcheo_sdk.mcp_server.config import get_api_client

    client, settings = get_api_client()
    assert client.base_url == "http://api.test"
    assert settings.api_url == "http://api.test"
    assert settings.service_token == "test-token"


def test_get_api_client_missing_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test API client raises error when URL is explicitly None."""
    from orcheo_sdk.mcp_server.config import get_api_client

    with patch("orcheo_sdk.mcp_server.config.resolve_settings") as mock_resolve:
        mock_settings = type(
            "CLISettings", (), {"api_url": None, "service_token": "test"}
        )()
        mock_resolve.return_value = mock_settings

        with pytest.raises(ValueError, match="ORCHEO_API_URL must be set"):
            get_api_client()


def test_create_server(mock_env: None) -> None:
    """Test MCP server creation."""
    from orcheo_sdk.mcp_server.main import create_server

    server = create_server()
    assert server is not None
    assert server.name == "Orcheo CLI"


def test_mcp_init_lazy_import() -> None:
    """Test lazy import in mcp_server __init__."""
    import orcheo_sdk.mcp_server

    create_server = orcheo_sdk.mcp_server.create_server
    assert create_server is not None

    with pytest.raises(AttributeError, match="has no attribute"):
        _ = orcheo_sdk.mcp_server.nonexistent_function


def test_main_entry_point(mock_env: None) -> None:
    """Test main entry point function."""
    from orcheo_sdk.mcp_server.main import main

    with patch("orcheo_sdk.mcp_server.main.mcp.run") as mock_run:
        main()
        mock_run.assert_called_once()
