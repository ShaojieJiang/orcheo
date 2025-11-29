"""Edge-related CLI commands."""

from __future__ import annotations
from typing import Annotated
import typer
from rich.console import Console
from orcheo_sdk.cli.output import render_json, render_table
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.services import list_edges_data, show_edge_data


edge_app = typer.Typer(help="Inspect available edges and their schemas.")

CategoryOption = Annotated[
    str | None,
    typer.Option("--category", help="Filter edges by category keyword."),
]
NameArgument = Annotated[
    str,
    typer.Argument(help="Edge name as registered in the catalog."),
]


def _get_console(ctx: typer.Context) -> Console:
    state: CLIState = ctx.ensure_object(CLIState)
    return state.console


@edge_app.command("list")
def list_edges(ctx: typer.Context, category: CategoryOption = None) -> None:
    """List registered edges with metadata."""
    console = _get_console(ctx)
    edges = list_edges_data(category=category)
    rows = [
        [
            item.get("name"),
            item.get("category"),
            item.get("description"),
        ]
        for item in edges
    ]
    render_table(
        console,
        title="Available Edges",
        columns=["Name", "Category", "Description"],
        rows=rows,
    )


@edge_app.command("show")
def show_edge(ctx: typer.Context, name: NameArgument) -> None:
    """Display metadata and schema information for ``name``."""
    console = _get_console(ctx)
    data = show_edge_data(name)

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
