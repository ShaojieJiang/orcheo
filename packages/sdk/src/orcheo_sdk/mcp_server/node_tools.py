"""Node metadata MCP tools."""

from orcheo_sdk.mcp_server import tools
from orcheo_sdk.mcp_server.server import mcp


@mcp.tool()
def list_nodes(tag: str | None = None) -> list[dict]:
    """List registered nodes optionally filtered by tag."""
    return tools.list_nodes(tag=tag)


@mcp.tool()
def show_node(name: str) -> dict:
    """Display metadata and schema for a node."""
    return tools.show_node(name=name)


__all__ = ["list_nodes", "show_node"]
