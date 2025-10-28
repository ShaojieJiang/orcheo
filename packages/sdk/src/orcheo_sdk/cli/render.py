"""Rendering helpers for CLI output."""

from __future__ import annotations
import re
from collections.abc import Iterable, Sequence
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table


def render_table(
    console: Console,
    *,
    title: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[str]],
) -> None:
    """Render a simple table using :mod:`rich`."""
    table = Table(title=title, show_lines=False)
    for column in columns:
        table.add_column(column)
    for row in rows:
        table.add_row(*row)
    console.print(table)


def render_kv_section(
    console: Console,
    *,
    title: str,
    pairs: Sequence[tuple[str, str]],
) -> None:
    """Render key/value pairs in a bordered panel."""
    lines = [f"[bold]{key}[/]: {value}" for key, value in pairs]
    panel = Panel("\n".join(lines), title=title, expand=False)
    console.print(panel)


_IDENTIFIER_RE = re.compile(r"[^0-9A-Za-z_]")


def _sanitize(identifier: str) -> str:
    normalized = identifier.strip() or "node"
    normalized = _IDENTIFIER_RE.sub("_", normalized)
    if normalized[0].isdigit():
        normalized = f"_{normalized}"
    return normalized


def graph_to_mermaid(graph: dict[str, object]) -> str:
    """Convert a workflow graph definition into Mermaid syntax."""
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return "flowchart TD\n    %% Invalid graph payload"

    lines = ["flowchart TD"]
    for node in nodes:
        if not isinstance(node, dict):
            continue
        name = str(node.get("name", "node"))
        type_name = str(node.get("type", ""))
        label = name
        if type_name:
            label = f"{name}\\n[{type_name}]"
        lines.append(f'    {_sanitize(name)}["{label}"]')

    for edge in edges:
        if not isinstance(edge, list | tuple) or len(edge) != 2:
            continue
        source, target = map(str, edge)
        lines.append(f"    {_sanitize(source)} --> {_sanitize(target)}")
    return "\n".join(lines)


def render_mermaid(console: Console, *, title: str, mermaid: str) -> None:
    """Print a Mermaid code block wrapped in a panel."""
    markdown = Markdown(f"```mermaid\n{mermaid}\n```", code_theme="default")
    panel = Panel(markdown, title=title, expand=False)
    console.print(panel)


__all__ = ["graph_to_mermaid", "render_kv_section", "render_mermaid", "render_table"]
