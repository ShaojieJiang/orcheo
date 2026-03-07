"""Shared MCP server configuration and lifecycle helpers."""

from fastmcp import FastMCP
from orcheo_sdk.mcp_server.config import validate_server_configuration


# Single FastMCP instance reused across all tool modules.
mcp = FastMCP("Orcheo CLI")


def create_server() -> FastMCP:
    """Ensure configuration is valid and return the MCP server."""
    validate_server_configuration()
    return mcp


def run_server() -> None:
    """Validate configuration and run the MCP server."""
    validate_server_configuration()
    mcp.run()


__all__ = ["create_server", "mcp", "run_server"]
