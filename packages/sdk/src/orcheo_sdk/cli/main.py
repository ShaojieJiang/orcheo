"""Orcheo CLI entrypoint."""

from __future__ import annotations
import os
import sys
from datetime import timedelta
from typing import Annotated
import click
import typer
from rich.console import Console
from orcheo_sdk.cli.agent_tool import agent_tool_app
from orcheo_sdk.cli.cache import CacheManager
from orcheo_sdk.cli.codegen import code_app
from orcheo_sdk.cli.config import get_cache_dir, resolve_settings
from orcheo_sdk.cli.credential import credential_app
from orcheo_sdk.cli.errors import APICallError, CLIConfigurationError, CLIError
from orcheo_sdk.cli.http import ApiClient
from orcheo_sdk.cli.node import node_app
from orcheo_sdk.cli.service_token import app as service_token_app
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.cli.workflow import workflow_app


def _is_completion_mode() -> bool:
    """Check if we're in shell completion mode."""
    return any(
        env_var.startswith("_TYPER_COMPLETE") or env_var.startswith("_ORCHEO_COMPLETE")
        for env_var in os.environ
    )


app = typer.Typer(help="Command line interface for Orcheo workflows.")
app.add_typer(node_app, name="node")
app.add_typer(workflow_app, name="workflow")
app.add_typer(credential_app, name="credential")
app.add_typer(code_app, name="code")
app.add_typer(agent_tool_app, name="agent-tool")
app.add_typer(service_token_app, name="token")


@app.callback()
def main(
    ctx: typer.Context,
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Profile name from the CLI config."),
    ] = None,
    api_url: Annotated[
        str | None,
        typer.Option("--api-url", help="Override the API URL."),
    ] = None,
    service_token: Annotated[
        str | None,
        typer.Option("--service-token", help="Override the service token."),
    ] = None,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Use cached data when network calls fail."),
    ] = False,
    cache_ttl_hours: Annotated[
        int,
        typer.Option("--cache-ttl", help="Cache TTL in hours for offline data."),
    ] = 24,
) -> None:
    """Configure shared CLI state and validate configuration."""
    # Skip expensive initialization during shell completion
    if _is_completion_mode():
        return  # pragma: no cover

    console = Console()
    try:
        settings = resolve_settings(
            profile=profile,
            api_url=api_url,
            service_token=service_token,
            offline=offline,
        )
    except CLIConfigurationError as exc:  # pragma: no cover
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    cache = CacheManager(
        directory=get_cache_dir(),
        ttl=timedelta(hours=cache_ttl_hours),
    )
    client = ApiClient(base_url=settings.api_url, token=settings.service_token)
    ctx.obj = CLIState(settings=settings, client=client, cache=cache, console=console)


def _print_cli_error(console: Console, exc: CLIError) -> None:
    """Print a concise, user-friendly error message for CLI errors."""
    error_msg = str(exc)

    # For authentication errors, provide helpful hints
    if isinstance(exc, APICallError):
        if exc.status_code == 401:
            console.print(f"[red]Error:[/red] {error_msg}")
            console.print(
                "\n[yellow]Hint:[/yellow] Authentication failed. "
                "Set ORCHEO_SERVICE_TOKEN environment variable or "
                "configure a profile with 'orcheo config'."
            )
            return
        elif exc.status_code == 403:
            console.print(f"[red]Error:[/red] {error_msg}")
            console.print(
                "\n[yellow]Hint:[/yellow] Your token lacks the required permissions."
            )
            return

    # Default: just print the error message without stack trace
    console.print(f"[red]Error:[/red] {error_msg}")


def run() -> None:
    """Entry point used by console scripts."""
    console = Console()
    try:
        app(standalone_mode=False)
    except click.UsageError as exc:
        console.print(f"[red]Error:[/red] {exc.message}")
        if exc.ctx and exc.ctx.command_path:
            help_cmd = f"{exc.ctx.command_path} --help"
            console.print(f"\nRun '[cyan]{help_cmd}[/cyan]' for usage information.")
        sys.exit(1)
    except CLIError as exc:
        _print_cli_error(console, exc)
        sys.exit(1)
