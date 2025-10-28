"""Output helpers for rendering data in the CLI."""

from __future__ import annotations
from typing import Any
from rich.console import Console
from rich.pretty import Pretty
from rich.table import Table
from rich.text import Text


def render_table(
    console: Console,
    *,
    title: str,
    columns: list[str],
    rows: list[list[Any]],
) -> None:
    """Render a table with ``columns`` and ``rows`` to ``console``."""
    table = Table(title=title, show_lines=False)
    for column in columns:
        table.add_column(column)
    for row in rows:
        table.add_row(*[str(cell) for cell in row])
    console.print(table)


def render_json(console: Console, payload: Any, *, title: str | None = None) -> None:
    """Render a JSON-like payload using Rich's pretty printer."""
    if title:
        console.print(Text(title, style="bold"))
    console.print(Pretty(payload, indent_guides=True))
