"""Agent tool-related CLI commands."""

from __future__ import annotations
from typing import Annotated
import typer
from rich.console import Console
from orcheo_sdk.cli.output import render_json, render_table
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


def _get_console(ctx: typer.Context) -> Console:
    """Get console from CLI state."""
    state: CLIState = ctx.ensure_object(CLIState)
    return state.console


@agent_tool_app.command("list")
def list_tools(ctx: typer.Context, category: CategoryOption = None) -> None:
    """List registered agent tools with metadata."""
    console = _get_console(ctx)
    tools = list_agent_tools_data(category=category)
    rows = [
        [
            item.get("name"),
            item.get("category"),
            item.get("description"),
        ]
        for item in tools
    ]
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
    data = show_agent_tool_data(name)

    console.print(f"[bold]{data['name']}[/bold] ({data['category']})")
    console.print(data["description"])

    schema = data.get("schema")
    if schema is not None:
        render_json(console, schema, title="Tool Schema")
    else:
        console.print("\n[dim]No schema information available[/dim]")
