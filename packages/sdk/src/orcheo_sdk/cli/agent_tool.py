"""Agent tool-related CLI commands."""

from __future__ import annotations
from typing import Annotated
import typer
from orcheo_sdk.cli.output import (
    print_json,
    print_markdown_table,
    render_json,
    render_table,
)
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.services import list_agent_tools_data, show_agent_tool_data


agent_tool_app = typer.Typer(help="Inspect available agent tools and their schemas.")

CategoryOption = Annotated[
    str | None,
    typer.Option("--category", help="Filter tools by category keyword."),
]
NameArgument = Annotated[
    str,
    typer.Argument(help="Tool name as registered in the catalog."),
]


def _state(ctx: typer.Context) -> CLIState:
    return ctx.ensure_object(CLIState)


@agent_tool_app.command("list")
def list_tools(ctx: typer.Context, category: CategoryOption = None) -> None:
    """List registered agent tools with metadata."""
    state = _state(ctx)
    tools = list_agent_tools_data(category=category)
    if not state.human:
        print_markdown_table(tools)
        return
    rows = [
        [
            item.get("name"),
            item.get("category"),
            item.get("description"),
        ]
        for item in tools
    ]
    render_table(
        state.console,
        title="Available Agent Tools",
        columns=["Name", "Category", "Description"],
        rows=rows,
    )


@agent_tool_app.command("show")
def show_tool(ctx: typer.Context, name: NameArgument) -> None:
    """Display metadata and schema information for a specific tool."""
    state = _state(ctx)
    data = show_agent_tool_data(name)
    if not state.human:
        print_json(data)
        return

    state.console.print(f"[bold]{data['name']}[/bold] ({data['category']})")
    state.console.print(data["description"])

    schema = data.get("schema")
    if schema is not None:
        render_json(state.console, schema, title="Tool Schema")
    else:
        state.console.print("\n[dim]No schema information available[/dim]")
