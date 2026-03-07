"""Edge metadata MCP tools."""

from orcheo_sdk.mcp_server import tools
from orcheo_sdk.mcp_server.server import mcp


@mcp.tool()
def list_edges(category: str | None = None) -> list[dict]:
    """List registered edges optionally filtered by category."""
    return tools.list_edges(category=category)


@mcp.tool()
def show_edge(name: str) -> dict:
    """Display metadata and schema for an edge."""
    return tools.show_edge(name=name)


__all__ = ["list_edges", "show_edge"]
