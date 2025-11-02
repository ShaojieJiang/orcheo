"""Node-related CLI commands."""

from __future__ import annotations
from importlib import import_module
from typing import TYPE_CHECKING, Annotated
import typer
from rich.console import Console
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.output import render_json, render_table
from orcheo_sdk.cli.state import CLIState


if TYPE_CHECKING:
    from orcheo.nodes.registry import NodeRegistry


node_app = typer.Typer(help="Inspect available nodes and their schemas.")

TagOption = Annotated[
    str | None,
    typer.Option("--tag", help="Filter nodes by category keyword."),
]
NameArgument = Annotated[
    str,
    typer.Argument(help="Node name as registered in the catalog."),
]


def _load_registry() -> NodeRegistry:
    """Load node registry lazily to avoid heavy dependencies on import."""
    from orcheo.nodes.registry import NodeRegistry

    module = import_module("orcheo.nodes.registry")
    registry = getattr(module, "registry", None)
    if not isinstance(registry, NodeRegistry):  # pragma: no cover - defensive
        msg = "Unable to load node registry from orcheo.nodes.registry"
        raise CLIError(msg)
    return registry


def _get_console(ctx: typer.Context) -> Console:
    state: CLIState = ctx.ensure_object(CLIState)
    return state.console


@node_app.command("list")
def list_nodes(ctx: typer.Context, tag: TagOption = None) -> None:
    """List registered nodes with metadata."""
    console = _get_console(ctx)
    registry = _load_registry()
    entries = registry.list_metadata()

    if tag:
        lowered = tag.lower()
        entries = [
            item
            for item in entries
            if lowered in item.category.lower() or lowered in item.name.lower()
        ]

    rows = [[item.name, item.category, item.description] for item in entries]
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
    registry = _load_registry()
    metadata = registry.get_metadata(name)
    node_cls = registry.get_node(name)
    if metadata is None or node_cls is None:
        raise CLIError(f"Node '{name}' is not registered.")

    console.print(f"[bold]{metadata.name}[/bold] ({metadata.category})")
    console.print(metadata.description)

    if hasattr(node_cls, "model_json_schema"):
        schema = node_cls.model_json_schema()
        render_json(console, schema, title="Pydantic schema")
    else:  # pragma: no cover - fallback for unexpected node implementations
        attributes = list(getattr(node_cls, "__annotations__", {}).keys())
        render_json(console, {"attributes": attributes})
