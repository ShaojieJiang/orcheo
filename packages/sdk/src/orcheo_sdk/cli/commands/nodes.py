"""Node catalog commands."""

from __future__ import annotations
import typer
from orcheo_sdk.cli import render as renderers
from orcheo_sdk.cli.runtime import CliError, CliRuntime, render_error, render_warning
from orcheo_sdk.cli.services import NodeRecord, fetch_node_catalog


node_app = typer.Typer(help="Discover available Orcheo nodes")


def _runtime(ctx: typer.Context) -> CliRuntime:
    runtime = ctx.obj
    if not isinstance(runtime, CliRuntime):  # pragma: no cover - defensive
        raise typer.Exit(code=1)
    return runtime


def _matches_tag(node: NodeRecord, candidate: str) -> bool:
    needle = candidate.strip().lower()
    if not needle:
        return True
    if node.category.lower() == needle:
        return True
    return any(tag.lower() == needle for tag in node.tags)


@node_app.command("list", help="List nodes available to the CLI")
def list_nodes(
    ctx: typer.Context,
    tag: str | None = typer.Option(
        None,
        "--tag",
        "-t",
        help="Filter nodes by tag or category",
    ),
) -> None:
    """Render the node catalog in a tabular format."""
    runtime = _runtime(ctx)
    try:
        nodes, _from_cache, cache_entry = fetch_node_catalog(runtime)
    except CliError as exc:
        render_error(runtime.console, str(exc))
        raise typer.Exit(code=1) from exc

    if tag:
        filtered = [node for node in nodes if _matches_tag(node, tag)]
        if not filtered:
            runtime.console.print("No nodes match the requested filter.")
            return
        nodes = filtered

    if cache_entry and runtime.cache.is_stale(cache_entry):
        render_warning(
            runtime.console,
            (
                "Node catalog cached data is older than 24 hours; "
                "refresh online for the latest metadata."
            ),
        )

    renderers.render_node_table(runtime.console, nodes)


@node_app.command("show", help="Display details for a specific node")
def show_node(ctx: typer.Context, name: str) -> None:
    """Display metadata for a single node."""
    runtime = _runtime(ctx)
    try:
        nodes, _from_cache, cache_entry = fetch_node_catalog(runtime)
    except CliError as exc:
        render_error(runtime.console, str(exc))
        raise typer.Exit(code=1) from exc

    target = next((node for node in nodes if node.name.lower() == name.lower()), None)
    if target is None:
        render_error(runtime.console, f"Node '{name}' was not found")
        raise typer.Exit(code=1)

    if cache_entry and runtime.cache.is_stale(cache_entry):
        render_warning(
            runtime.console,
            (
                "Node metadata is served from a cache older than 24 hours; "
                "refresh online to update."
            ),
        )

    runtime.console.print(f"Name: {target.name}")
    runtime.console.print(f"Category: {target.category}")
    runtime.console.print(f"Description: {target.description or '—'}")
    runtime.console.print(f"Tags: {', '.join(target.tags) if target.tags else '—'}")
