"""Node-related CLI commands."""

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


def _state(ctx: typer.Context) -> CLIState:
    return ctx.ensure_object(CLIState)


@node_app.command("list")
def list_nodes(ctx: typer.Context, tag: TagOption = None) -> None:
    """List registered nodes with metadata."""
    state = _state(ctx)
    nodes = list_nodes_data(tag=tag)
    if not state.human:
        print_markdown_table(nodes)
        return
    rows = [
        [
            item.get("name"),
            item.get("category"),
            item.get("description"),
        ]
        for item in nodes
    ]
    render_table(
        state.console,
        title="Available Nodes",
        columns=["Name", "Category", "Description"],
        rows=rows,
    )


@node_app.command("show")
def show_node(ctx: typer.Context, name: NameArgument) -> None:
    """Display metadata and schema information for ``name``."""
    state = _state(ctx)
    data = show_node_data(name)
    if not state.human:
        print_json(data)
        return

    state.console.print(f"[bold]{data['name']}[/bold] ({data['category']})")
    state.console.print(data["description"])

    schema = data.get("schema")
    if schema is not None:
        render_json(state.console, schema, title="Pydantic schema")
        return

    attributes = data.get("attributes")
    if attributes:
        render_json(state.console, {"attributes": attributes})
    else:  # pragma: no cover - fallback when neither schema nor attributes present
        state.console.print("\n[dim]No schema information available[/dim]")
