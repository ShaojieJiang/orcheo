"""Agent tool discovery MCP bindings."""

from orcheo_sdk.mcp_server import tools
from orcheo_sdk.mcp_server.server import mcp


@mcp.tool()
def list_agent_tools(category: str | None = None) -> list[dict]:
    """List registered agent tools optionally filtered by category."""
    return tools.list_agent_tools(category=category)


@mcp.tool()
def show_agent_tool(name: str) -> dict:
    """Display metadata for a specific agent tool."""
    return tools.show_agent_tool(name=name)


__all__ = ["list_agent_tools", "show_agent_tool"]
