"""Tools for AI agents."""

from langchain_core.tools import tool
from orcheo.nodes.agent_tools.registry import ToolMetadata, tool_registry


@tool_registry.register(
    ToolMetadata(
        name="greet_user",
        description="Print a greeting to the user.",
        category="general",
    )
)
@tool
def greet_user(username: str) -> str:
    """Print a greeting to the user."""
    return f"Hello, {username}!"
