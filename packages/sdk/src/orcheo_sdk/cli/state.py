"""Shared CLI state passed between Typer commands."""

from __future__ import annotations
from dataclasses import dataclass
from rich.console import Console
from orcheo_sdk.cli.cache import CacheManager
from orcheo_sdk.cli.config import CLISettings
from orcheo_sdk.cli.http import ApiClient


@dataclass(slots=True)
class CLIState:
    """Runtime state shared across commands."""

    settings: CLISettings
    client: ApiClient
    cache: CacheManager
    console: Console
    verbose_results: bool = False
