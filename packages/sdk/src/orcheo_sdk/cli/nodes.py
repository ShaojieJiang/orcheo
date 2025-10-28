"""Node discovery commands."""

from __future__ import annotations
from typing import Any
import typer
from .api import ApiRequestError, OfflineCacheMissError
from .render import render_kv_section, render_table
from .utils import abort_with_error, get_context, show_cache_notice


node_app = typer.Typer(help="Inspect available Orcheo nodes.")


@node_app.command("list")
def list_nodes(
    ctx: typer.Context,
    tag: str = typer.Option(None, help="Filter nodes by tag."),
    category: str = typer.Option(None, help="Filter nodes by category."),
) -> None:
    """Display the node catalog."""
    context = get_context(ctx)
    params: dict[str, str] = {}
    if tag:
        params["tag"] = tag
    if category:
        params["category"] = category

    try:
        result = context.client.get_json(
            "/nodes/catalog",
            params=params or None,
            offline=context.offline,
            description="node catalog",
        )
    except OfflineCacheMissError as exc:
        context.console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except ApiRequestError as exc:
        abort_with_error(context, exc)

    entries = result.data if isinstance(result.data, list) else []
    rows: list[tuple[str, str, str, str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", ""))
        type_name = str(entry.get("type", ""))
        version = str(entry.get("version", ""))
        category_value = str(entry.get("category", ""))
        tags_value = ""
        tags = entry.get("tags")
        if isinstance(tags, list):
            tags_value = ", ".join(str(tag) for tag in tags)
        rows.append((name, type_name, version, category_value, tags_value))

    if not rows:
        context.console.print("[yellow]No nodes found.[/yellow]")
    else:
        render_table(
            context.console,
            title="Node Catalog",
            columns=("Name", "Type", "Version", "Category", "Tags"),
            rows=rows,
        )

    if result.from_cache:
        show_cache_notice(context, result.timestamp)


@node_app.command("show")
def show_node(
    ctx: typer.Context,
    node: str = typer.Argument(..., help="Node identifier to inspect."),
) -> None:
    """Show metadata for a single node."""
    context = get_context(ctx)

    try:
        result = context.client.get_json(
            f"/nodes/catalog/{node}",
            offline=context.offline,
            description="node details",
        )
    except OfflineCacheMissError as exc:
        context.console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except ApiRequestError as exc:
        abort_with_error(context, exc)

    payload = result.data if isinstance(result.data, dict) else {}

    metadata_pairs = [
        ("Name", str(payload.get("name", node))),
        ("Type", str(payload.get("type", "unknown"))),
        ("Version", str(payload.get("version", "n/a"))),
        ("Category", str(payload.get("category", "general"))),
        ("Description", str(payload.get("description", ""))),
    ]
    render_kv_section(context.console, title="Node", pairs=metadata_pairs)

    inputs = payload.get("inputs")
    if isinstance(inputs, list) and inputs:
        input_rows = _schema_rows(inputs)
        render_table(
            context.console,
            title="Inputs",
            columns=("Name", "Type", "Required", "Description"),
            rows=input_rows,
        )

    outputs = payload.get("outputs")
    if isinstance(outputs, list) and outputs:
        output_rows = _schema_rows(outputs)
        render_table(
            context.console,
            title="Outputs",
            columns=("Name", "Type", "Required", "Description"),
            rows=output_rows,
        )

    credentials = payload.get("credentials")
    if isinstance(credentials, list) and credentials:
        credential_rows: list[tuple[str, str]] = []
        for cred in credentials:
            if not isinstance(cred, dict):
                continue
            credential_rows.append(
                (
                    str(cred.get("name", "")),
                    str(cred.get("description", "")),
                )
            )
        render_table(
            context.console,
            title="Credential Requirements",
            columns=("Credential", "Description"),
            rows=credential_rows,
        )

    if result.from_cache:
        show_cache_notice(context, result.timestamp)


def _schema_rows(items: list[Any]) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", ""))
        type_name = str(item.get("type", ""))
        required_flag = str(item.get("required", False))
        description = str(item.get("description", ""))
        rows.append((name, type_name, required_flag, description))
    return rows


__all__ = ["node_app"]
