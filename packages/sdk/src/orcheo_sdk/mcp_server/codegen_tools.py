"""Code generation related MCP tools."""

from orcheo_sdk.mcp_server import tools
from orcheo_sdk.mcp_server.server import mcp


@mcp.tool()
def generate_workflow_scaffold(
    workflow_id: str,
    actor: str = "mcp",
    profile: str | None = None,
) -> dict:
    """Generate Python snippet to trigger a workflow."""
    return tools.generate_workflow_scaffold(
        workflow_id=workflow_id,
        actor=actor,
        profile=profile,
    )


@mcp.tool()
def generate_workflow_template() -> dict:
    """Generate a minimal LangGraph workflow template."""
    return tools.generate_workflow_template()


__all__ = ["generate_workflow_scaffold", "generate_workflow_template"]
