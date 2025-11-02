"""Agent tool-related CLI commands."""

from __future__ import annotations
from importlib import import_module
from typing import TYPE_CHECKING, Annotated, Any
import typer
from rich.console import Console
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.output import render_json, render_table
from orcheo_sdk.cli.state import CLIState


if TYPE_CHECKING:
    from orcheo.nodes.agent_tools.registry import ToolRegistry


agent_tool_app = typer.Typer(help="Inspect available agent tools and their schemas.")

CategoryOption = Annotated[
    str | None,
    typer.Option("--category", help="Filter tools by category keyword."),
]
NameArgument = Annotated[
    str,
    typer.Argument(help="Tool name as registered in the catalog."),
]


def _load_registry() -> ToolRegistry:
    """Load the global tool registry from orcheo.nodes.agent_tools.registry."""
    from orcheo.nodes.agent_tools.registry import ToolRegistry

    try:
        # Import tools module to trigger registration
        import_module("orcheo.nodes.agent_tools.tools")
    except ModuleNotFoundError as exc:  # pragma: no cover - import error
        msg = "Unable to import orcheo.nodes.agent_tools.tools for registry population"
        raise CLIError(msg) from exc

    try:
        module = import_module("orcheo.nodes.agent_tools.registry")
    except ModuleNotFoundError as exc:  # pragma: no cover - import error
        msg = "Unable to import orcheo.nodes.agent_tools.registry"
        raise CLIError(msg) from exc

    registry = getattr(module, "tool_registry", None)
    if registry is None:  # pragma: no cover - defensive
        msg = (
            "orcheo.nodes.agent_tools.registry does not expose "
            "a 'tool_registry' attribute"
        )
        raise CLIError(msg)

    if not isinstance(registry, ToolRegistry):  # pragma: no cover - defensive
        msg = "Loaded registry is not an instance of ToolRegistry"
        raise CLIError(msg)
    return registry


def _get_console(ctx: typer.Context) -> Console:
    """Get console from CLI state."""
    state: CLIState = ctx.ensure_object(CLIState)
    return state.console


@agent_tool_app.command("list")
def list_tools(ctx: typer.Context, category: CategoryOption = None) -> None:
    """List registered agent tools with metadata."""
    console = _get_console(ctx)
    registry = _load_registry()
    entries = registry.list_metadata()

    if category:
        lowered = category.lower()
        entries = [
            item
            for item in entries
            if lowered in item.category.lower() or lowered in item.name.lower()
        ]

    rows = [[item.name, item.category, item.description] for item in entries]
    render_table(
        console,
        title="Available Agent Tools",
        columns=["Name", "Category", "Description"],
        rows=rows,
    )


@agent_tool_app.command("show")
def show_tool(ctx: typer.Context, name: NameArgument) -> None:
    """Display metadata and schema information for a specific tool."""
    console = _get_console(ctx)
    registry = _load_registry()
    metadata = registry.get_metadata(name)
    tool = registry.get_tool(name)
    if metadata is None or tool is None:
        raise CLIError(f"Agent tool '{name}' is not registered.")

    console.print(f"[bold]{metadata.name}[/bold] ({metadata.category})")
    console.print(metadata.description)

    # Try to extract schema from the tool
    schema_data: dict[str, Any] = {}
    if hasattr(tool, "args_schema") and tool.args_schema is not None:
        # LangChain tool with Pydantic schema
        if hasattr(tool.args_schema, "model_json_schema"):
            schema_data = tool.args_schema.model_json_schema()
    elif hasattr(tool, "model_json_schema"):
        # Direct Pydantic model
        schema_data = tool.model_json_schema()
    elif hasattr(tool, "__annotations__"):
        # Function with type annotations
        annotations = getattr(tool, "__annotations__", {})
        if annotations:
            schema_data = {
                "type": "object",
                "properties": {
                    key: {"type": str(val)} for key, val in annotations.items()
                },
            }
    else:  # pragma: no cover - fallback for unexpected tool implementations
        pass

    if schema_data:
        render_json(console, schema_data, title="Tool Schema")
    else:
        console.print("\n[dim]No schema information available[/dim]")
