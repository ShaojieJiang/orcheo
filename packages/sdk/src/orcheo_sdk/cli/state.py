"""Runtime state shared across CLI commands."""

from __future__ import annotations
from dataclasses import dataclass
from rich.console import Console
from .api import APIClient
from .cache import CacheStore
from .config import CLISettings


@dataclass(slots=True)
class CLIContext:
    """Object stored on :class:`typer.Context` for command access."""

    settings: CLISettings
    client: APIClient
    cache: CacheStore
    console: Console
    offline: bool = False


__all__ = ["CLIContext"]
