"""Typer application wiring for the Orcheo CLI."""

from __future__ import annotations
from pathlib import Path
from typing import Annotated
import typer
from rich.console import Console
from .api import APIClient
from .cache import CacheStore
from .code import code_app
from .config import ProfileNotFoundError, resolve_settings
from .credentials import credential_app
from .nodes import node_app
from .state import CLIContext
from .workflows import workflow_app


app = typer.Typer(help="Command line tools for the Orcheo platform.")
app.add_typer(node_app, name="node")
app.add_typer(workflow_app, name="workflow")
app.add_typer(credential_app, name="credential")
app.add_typer(code_app, name="code")


@app.callback()
def _configure(
    ctx: typer.Context,
    api_url: Annotated[
        str | None,
        typer.Option(help="Override the Orcheo API URL."),
    ] = None,
    service_token: Annotated[
        str | None,
        typer.Option(help="Service token used for authentication."),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Named profile from the CLI config file.",
        ),
    ] = None,
    offline: Annotated[
        bool,
        typer.Option(
            help="Serve data from cache without network calls.",
        ),
    ] = False,
    config_path: Annotated[
        Path | None,
        typer.Option(help="Path to cli.toml with saved profiles."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option(help="Directory for cached responses."),
    ] = None,
) -> None:
    """Initialise shared CLI state before executing a command."""
    try:
        settings = resolve_settings(
            api_url=api_url,
            service_token=service_token,
            profile=profile,
            config_path=config_path,
            cache_dir=cache_dir,
        )
    except ProfileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc

    cache = CacheStore(settings.cache_dir)
    cache.ensure()

    base_url = settings.api_url.rstrip("/")
    if not base_url.endswith("/api"):
        base_url = f"{base_url}/api"

    client = APIClient(
        base_url=base_url,
        service_token=settings.service_token,
        cache=cache,
    )
    console = Console()

    ctx.obj = CLIContext(
        settings=settings, client=client, cache=cache, console=console, offline=offline
    )
    ctx.call_on_close(client.close)


def main() -> None:
    """Entry point for console script execution."""
    app()


__all__ = ["app", "main"]
