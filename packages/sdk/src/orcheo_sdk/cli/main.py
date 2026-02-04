"""Orcheo CLI entrypoint."""

from __future__ import annotations
import os
import sys
from collections.abc import Callable
from datetime import timedelta
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from typing import Annotated, Any
import click
import typer
from rich.console import Console
from orcheo_sdk.cli.agent_tool import agent_tool_app
from orcheo_sdk.cli.auth import auth_app
from orcheo_sdk.cli.cache import CacheManager
from orcheo_sdk.cli.codegen import code_app
from orcheo_sdk.cli.config import get_cache_dir, resolve_settings
from orcheo_sdk.cli.config_command import config_app
from orcheo_sdk.cli.credential import credential_app
from orcheo_sdk.cli.edge import edge_app
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


def _version_callback(value: bool) -> None:
    """Print CLI version and exit."""
    if not value:
        return
    try:
        version_value = package_version("orcheo-sdk")
    except PackageNotFoundError:
        version_value = "unknown"
    typer.echo(f"orcheo {version_value}")
    raise typer.Exit()


app = typer.Typer(help="Command line interface for Orcheo workflows.")
app.add_typer(auth_app, name="auth")
app.add_typer(node_app, name="node")
app.add_typer(edge_app, name="edge")
app.add_typer(workflow_app, name="workflow")
app.add_typer(credential_app, name="credential")
app.add_typer(code_app, name="code")
app.add_typer(config_app, name="config")
app.add_typer(agent_tool_app, name="agent-tool")
app.add_typer(service_token_app, name="token")


def _create_token_provider(profile: str | None) -> Callable[[], str | None]:
    """Create a token provider callback for OAuth token resolution."""

    def provider() -> str | None:
        from orcheo_sdk.cli.auth.refresh import get_valid_access_token

        return get_valid_access_token(profile=profile)

    return provider


@app.callback()
def main(
    ctx: typer.Context,
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Profile name from the CLI config."),
    ] = None,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show the Orcheo CLI version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
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
    human: Annotated[
        bool,
        typer.Option(
            "--human",
            help="Use human-friendly Rich output instead of machine-readable format.",
        ),
    ] = False,
) -> None:
    """Configure shared CLI state and validate configuration."""
    # Skip expensive initialization during shell completion
    if _is_completion_mode():
        return  # pragma: no cover

    resolved_human = human or bool(os.getenv("ORCHEO_HUMAN"))
    console = Console() if resolved_human else Console(no_color=True, highlight=False)
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
    client = ApiClient(
        base_url=settings.api_url,
        token=settings.service_token,
        public_base_url=settings.chatkit_public_base_url,
        token_provider=_create_token_provider(settings.profile),
    )
    ctx.obj = CLIState(
        settings=settings,
        client=client,
        cache=cache,
        console=console,
        human=resolved_human,
    )


def _print_cli_error(console: Console, exc: CLIError) -> None:
    """Print a concise, user-friendly error message for CLI errors."""
    error_msg = str(exc)

    # For authentication errors, provide helpful hints
    if isinstance(exc, APICallError):
        if exc.status_code == 401:
            console.print(f"[red]Error:[/red] {error_msg}")
            console.print(
                "\n[yellow]Hint:[/yellow] Authentication failed. "
                "Run 'orcheo auth login' to authenticate via OAuth, or "
                "set ORCHEO_SERVICE_TOKEN environment variable."
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


def _print_cli_error_machine(exc: CLIError) -> None:
    """Print a machine-readable error as JSON."""
    from orcheo_sdk.cli.output import print_json

    error_data: dict[str, Any] = {"error": str(exc)}
    if isinstance(exc, APICallError) and exc.status_code is not None:
        error_data["status_code"] = exc.status_code
    print_json(error_data)


def run() -> None:
    """Entry point used by console scripts."""
    human_mode = bool(os.getenv("ORCHEO_HUMAN")) or "--human" in sys.argv
    if not human_mode:
        app.rich_markup_mode = None
    console = Console()
    try:
        app(standalone_mode=False)
    except click.UsageError as exc:
        if human_mode:
            console.print(f"[red]Error:[/red] {exc.message}")
            if exc.ctx and exc.ctx.command_path:
                help_cmd = f"{exc.ctx.command_path} --help"
                console.print(f"\nRun '[cyan]{help_cmd}[/cyan]' for usage information.")
        else:
            from orcheo_sdk.cli.output import print_json

            error_data: dict[str, Any] = {"error": exc.message}
            if exc.ctx and exc.ctx.command_path:
                error_data["help"] = f"{exc.ctx.command_path} --help"
            print_json(error_data)
        sys.exit(1)
    except CLIError as exc:
        if human_mode:
            _print_cli_error(console, exc)
        else:
            _print_cli_error_machine(exc)
        sys.exit(1)
