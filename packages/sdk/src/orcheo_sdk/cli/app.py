"""Typer application wiring the Orcheo CLI."""

from __future__ import annotations
import typer
from orcheo_sdk.cli.commands.code import code_app
from orcheo_sdk.cli.commands.credentials import credential_app
from orcheo_sdk.cli.commands.nodes import node_app
from orcheo_sdk.cli.commands.workflows import workflow_app
from orcheo_sdk.cli.runtime import (
    ApiClient,
    CacheStore,
    CliError,
    CliRuntime,
    build_console,
    default_cache_path,
    render_error,
    resolve_settings,
)


app = typer.Typer(help="Command line tooling for the Orcheo platform")
app.add_typer(node_app, name="node")
app.add_typer(workflow_app, name="workflow")
app.add_typer(credential_app, name="credential")
app.add_typer(code_app, name="code")


@app.callback()
def _configure(
    ctx: typer.Context,
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="Override the Orcheo API URL",
    ),
    service_token: str | None = typer.Option(
        None,
        "--service-token",
        help="Service token used for API authentication",
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Named profile to load from the CLI configuration file",
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Run commands without network access when supported",
    ),
    timeout: float = typer.Option(
        30.0,
        "--timeout",
        help="HTTP request timeout in seconds",
    ),
) -> None:
    """Initialise shared runtime objects for downstream commands."""
    try:
        settings = resolve_settings(
            api_url=api_url,
            service_token=service_token,
            profile=profile,
            timeout=timeout,
        )
    except CliError as exc:
        console = build_console()
        render_error(console, str(exc))
        raise typer.Exit(code=1) from exc

    console = build_console()
    cache_dir = default_cache_path()
    cache = CacheStore(cache_dir)
    runtime = CliRuntime(
        settings=settings,
        console=console,
        cache=cache,
        offline=offline,
    )

    if not offline:
        api_client = ApiClient(
            settings.api_url,
            service_token=settings.service_token,
            timeout=settings.timeout,
        )
        runtime.api = api_client
        ctx.call_on_close(api_client.close)

    ctx.obj = runtime


def main() -> None:
    """Console script entry point."""
    app()
