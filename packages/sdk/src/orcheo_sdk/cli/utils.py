"""Shared helpers used across CLI command modules."""

from __future__ import annotations
from datetime import datetime
import typer
from .api import ApiRequestError
from .state import CLIContext


def get_context(ctx: typer.Context) -> CLIContext:
    """Return the CLI context stored on the Typer context object."""
    obj = ctx.ensure_object(CLIContext)
    if not isinstance(obj, CLIContext):  # pragma: no cover - defensive branch
        msg = "CLI context has not been initialised"
        raise RuntimeError(msg)
    return obj


def abort_with_error(context: CLIContext, exc: ApiRequestError) -> None:
    """Print an API error and exit the CLI with a non-zero status code."""
    context.console.print(f"[red]{exc}[/red]")
    raise typer.Exit(code=1)


def show_cache_notice(context: CLIContext, result_timestamp: datetime | None) -> None:
    """Display a note when cached data is rendered."""
    if result_timestamp is None:
        return
    context.console.print(
        f"[dim]Served from cache last updated at {result_timestamp.isoformat()}[/dim]"
    )


__all__ = ["abort_with_error", "get_context", "show_cache_notice"]
