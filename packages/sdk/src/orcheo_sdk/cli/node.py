"""Node-related CLI commands."""

from __future__ import annotations
from typing import Annotated
import typer
from rich.console import Console
from orcheo_sdk.cli.output import render_json, render_table
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.services import list_nodes_data, show_node_data


node_app = typer.Typer(help="Inspect available nodes and their schemas.")

TagOption = Annotated[
    str | None,
    typer.Option("--tag", help="Filter nodes by category keyword."),
]
NameArgument = Annotated[
    str,
    typer.Argument(help="Node name as registered in the catalog."),
]


def _get_console(ctx: typer.Context) -> Console:
    state: CLIState = ctx.ensure_object(CLIState)
    return state.console


@node_app.command("list")
def list_nodes(ctx: typer.Context, tag: TagOption = None) -> None:
    """List registered nodes with metadata."""
    console = _get_console(ctx)
    nodes = list_nodes_data(tag=tag)
    rows = [
        [
            item.get("name"),
            item.get("category"),
            item.get("description"),
        ]
        for item in nodes
    ]
    render_table(
        console,
        title="Available Nodes",
        columns=["Name", "Category", "Description"],
        rows=rows,
    )


@node_app.command("show")
def show_node(ctx: typer.Context, name: NameArgument) -> None:
    """Display metadata and schema information for ``name``."""
    console = _get_console(ctx)
    data = show_node_data(name)

    console.print(f"[bold]{data['name']}[/bold] ({data['category']})")
    console.print(data["description"])

    schema = data.get("schema")
    if schema is not None:
        render_json(console, schema, title="Pydantic schema")
        return

    attributes = data.get("attributes")
    if attributes:
        render_json(console, {"attributes": attributes})
    else:  # pragma: no cover - fallback when neither schema nor attributes present
        console.print("\n[dim]No schema information available[/dim]")
