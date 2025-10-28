"""Node discovery commands."""

from __future__ import annotations
import inspect
from importlib import import_module
from typing import TYPE_CHECKING, Any
import typer
from .api import ApiRequestError, OfflineCacheMissError
from .render import render_kv_section, render_table
from .utils import abort_with_error, get_context, show_cache_notice


if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from collections.abc import Iterable
    from orcheo.nodes.registry import NodeMetadata, NodeRegistry


class NodeRegistryUnavailableError(RuntimeError):
    """Raised when the local Orcheo node registry cannot be loaded."""


node_app = typer.Typer(help="Inspect available Orcheo nodes.", add_completion=True)


@node_app.command("list")
def list_nodes(
    ctx: typer.Context,
    tag: str = typer.Option(None, help="Filter nodes by tag."),
    category: str = typer.Option(None, help="Filter nodes by category."),
) -> None:
    """Display the node catalog."""
    context = get_context(ctx)
    try:
        registry = _get_node_registry()
    except NodeRegistryUnavailableError as exc:  # pragma: no cover - defensive guard
        context.console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    rows = _build_node_rows(registry, tag=tag, category=category)
    if not rows:
        context.console.print("[yellow]No nodes found.[/yellow]")
        return

    render_table(
        context.console,
        title="Node Catalog",
        columns=("Name", "Kind", "Category", "Description"),
        rows=rows,
    )


def _get_node_registry() -> NodeRegistry:
    """Return the active Orcheo node registry instance."""
    try:
        import_module("orcheo.nodes")
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on environment
        msg = "Orcheo core is not installed."
        raise NodeRegistryUnavailableError(msg) from exc
    except Exception as exc:  # pragma: no cover - defensive guard
        msg = "Failed to import Orcheo nodes."
        raise NodeRegistryUnavailableError(msg) from exc

    try:
        from orcheo.nodes.registry import registry as core_registry
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on environment
        msg = "Orcheo node registry is unavailable."
        raise NodeRegistryUnavailableError(msg) from exc

    if not hasattr(core_registry, "iter_metadata"):
        msg = "Installed Orcheo core version does not expose node metadata."
        raise NodeRegistryUnavailableError(msg)

    return core_registry


def _build_node_rows(
    registry: NodeRegistry,
    *,
    tag: str | None,
    category: str | None,
) -> list[tuple[str, str, str, str]]:
    """Return display rows for the supplied ``registry``."""
    try:
        metadata_iter: Iterable[tuple[str, NodeMetadata]] = registry.iter_metadata()
    except AttributeError as exc:  # pragma: no cover - old registry versions
        msg = "Node registry does not support metadata iteration."
        raise NodeRegistryUnavailableError(msg) from exc

    rows: list[tuple[str, str, str, str]] = []
    category_filter = category.casefold() if category else None
    for name, metadata in metadata_iter:
        node_name = str(getattr(metadata, "name", name))
        node_category = str(getattr(metadata, "category", "general"))
        if category_filter and node_category.casefold() != category_filter:
            continue
        if tag and not _metadata_matches_tag(metadata, tag):
            continue
        implementation = registry.get_node(name)
        kind = _node_kind(implementation)
        description = str(getattr(metadata, "description", ""))
        rows.append((node_name, kind, node_category, description))

    rows.sort(key=lambda row: row[0].casefold())
    return rows


def _metadata_matches_tag(metadata: NodeMetadata, tag: str) -> bool:
    """Return True when ``metadata`` should be included for ``tag``."""
    needle = tag.casefold()
    tags = getattr(metadata, "tags", None)
    if isinstance(tags, list):
        for candidate in tags:
            if needle in str(candidate).casefold():
                return True

    text_fields = (
        getattr(metadata, "name", ""),
        getattr(metadata, "description", ""),
        getattr(metadata, "category", ""),
    )
    return any(
        isinstance(field, str) and needle in field.casefold() for field in text_fields
    )


def _node_kind(implementation: Any) -> str:
    """Return a friendly type label for ``implementation``."""
    if implementation is None:
        return "unknown"

    candidate = (
        implementation if inspect.isclass(implementation) else implementation.__class__
    )

    try:
        triggers_module = import_module("orcheo.nodes.triggers")
        trigger_node_cls = getattr(triggers_module, "TriggerNode", None)
    except Exception:  # pragma: no cover - optional dependency safety
        trigger_node_cls = None

    try:
        base_module = import_module("orcheo.nodes.base")
        ai_node_cls = getattr(base_module, "AINode", None)
        decision_node_cls = getattr(base_module, "DecisionNode", None)
        task_node_cls = getattr(base_module, "TaskNode", None)
    except Exception:  # pragma: no cover - optional dependency safety
        ai_node_cls = decision_node_cls = task_node_cls = None

    try:
        if trigger_node_cls and issubclass(candidate, trigger_node_cls):
            return "trigger"
        if ai_node_cls and issubclass(candidate, ai_node_cls):
            return "ai"
        if decision_node_cls and issubclass(candidate, decision_node_cls):
            return "decision"
        if task_node_cls and issubclass(candidate, task_node_cls):
            return "task"
    except TypeError:  # pragma: no cover - guard for unusual callables
        pass

    return getattr(candidate, "__name__", type(implementation).__name__)


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
