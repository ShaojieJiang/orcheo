"""Output helpers for rendering data in the CLI."""

from __future__ import annotations
import json
from datetime import datetime
from typing import Any, Literal
from rich.console import Console
from rich.pretty import Pretty
from rich.table import Table
from rich.text import Text


OverflowOption = Literal["fold", "crop", "ellipsis", "ignore"]


def render_table(
    console: Console,
    *,
    title: str,
    columns: list[str],
    rows: list[list[Any]],
    column_overflow: dict[str, OverflowOption] | None = None,
) -> None:
    """Render a table with ``columns`` and ``rows`` to ``console``."""
    overflow: dict[str, OverflowOption] = column_overflow or {}
    table = Table(title=title, show_lines=False)
    for column in columns:
        default_overflow: OverflowOption = "ellipsis"
        table.add_column(column, overflow=overflow.get(column, default_overflow))
    for row in rows:
        table.add_row(*[str(cell) for cell in row])
    console.print(table)


def render_json(console: Console, payload: Any, *, title: str | None = None) -> None:
    """Render a JSON-like payload using Rich's pretty printer."""
    if title:
        console.print(Text(title, style="bold"))
    console.print(Pretty(payload, indent_guides=True))


def format_datetime(iso_string: str) -> str:
    """Format an ISO datetime string for display."""
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        return iso_string


def success(message: str) -> None:
    """Print a success message."""
    console = Console()
    console.print(f"[green]✓ {message}[/green]")


def warning(message: str) -> None:
    """Print a warning message."""
    console = Console()
    console.print(f"[yellow]⚠ {message}[/yellow]")


def _escape_md_cell(value: str) -> str:
    """Escape pipe characters in a Markdown table cell."""
    return value.replace("|", "\\|")


def print_markdown_table(data: list[dict[str, Any]]) -> None:
    """Render a list of dicts as a Markdown table to stdout."""
    if not data:
        print("(empty)")
        return
    keys = list(data[0].keys())
    header = "| " + " | ".join(keys) + " |"
    separator = "| " + " | ".join("---" for _ in keys) + " |"
    rows: list[str] = []
    for item in data:
        cells = [_escape_md_cell(str(item.get(k, ""))) for k in keys]
        rows.append("| " + " | ".join(cells) + " |")
    print("\n".join([header, separator, *rows]))


def print_json(data: Any) -> None:
    """Print data as indented JSON to stdout."""
    print(json.dumps(data, indent=2, default=str))


def machine_success(message: str) -> None:
    """Print a success message as JSON for machine consumption."""
    print_json({"status": "success", "message": message})


def machine_warning(message: str) -> None:
    """Print a warning message as JSON for machine consumption."""
    print_json({"status": "warning", "message": message})
