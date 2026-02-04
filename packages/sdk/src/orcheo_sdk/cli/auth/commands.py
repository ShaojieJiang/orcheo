"""CLI commands for OAuth authentication."""

from __future__ import annotations
from typing import Annotated
import typer
from rich.table import Table
from orcheo_sdk.cli.auth.oauth import logout_oauth, start_oauth_login
from orcheo_sdk.cli.auth.tokens import (
    get_oauth_tokens,
    get_token_expiry_display,
    is_oauth_token_valid,
)
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.output import machine_success, print_json
from orcheo_sdk.cli.state import CLIState


auth_app = typer.Typer(name="auth", help="Manage OAuth authentication.")


def _state(ctx: typer.Context) -> CLIState:
    return ctx.ensure_object(CLIState)


@auth_app.command("login")
def login(
    ctx: typer.Context,
    no_browser: Annotated[
        bool,
        typer.Option(
            "--no-browser", help="Print the login URL instead of opening browser."
        ),
    ] = False,
    port: Annotated[
        int,
        typer.Option("--port", help="Local callback server port."),
    ] = 8085,
) -> None:
    """Authenticate with Orcheo via browser-based OAuth."""
    state = _state(ctx)
    try:
        start_oauth_login(
            console=state.console,
            profile=state.settings.profile,
            no_browser=no_browser,
            port=port,
        )
    except CLIError as exc:
        if state.human:
            state.console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        print_json({"error": str(exc)})
        raise typer.Exit(code=1) from exc


@auth_app.command("logout")
def logout(ctx: typer.Context) -> None:
    """Clear stored OAuth tokens for the current profile."""
    state = _state(ctx)
    logout_oauth(profile=state.settings.profile)
    if not state.human:
        machine_success("Logged out successfully.")
        return
    state.console.print("[green]Logged out successfully.[/green]")


@auth_app.command("status")
def status(ctx: typer.Context) -> None:
    """Show current authentication status."""
    state = _state(ctx)
    tokens = get_oauth_tokens(profile=state.settings.profile)

    if not state.human:
        status_data: dict[str, str | None] = {
            "profile": state.settings.profile or "default",
            "api_url": state.settings.api_url,
        }
        if tokens and is_oauth_token_valid(tokens):
            status_data["status"] = "authenticated"
            status_data["method"] = "oauth"
            status_data["expires"] = get_token_expiry_display(tokens)
        elif state.settings.service_token:
            status_data["status"] = "authenticated"
            status_data["method"] = "service_token"
        else:
            status_data["status"] = "not_authenticated"
        print_json(status_data)
        return

    table = Table(title="Authentication Status", show_header=False, box=None)
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Profile", state.settings.profile or "default")

    if tokens and is_oauth_token_valid(tokens):
        table.add_row("Status", "[green]Authenticated (OAuth)[/green]")
        table.add_row("Expires", get_token_expiry_display(tokens))
    elif state.settings.service_token:
        table.add_row("Status", "[green]Authenticated (Service Token)[/green]")
        table.add_row("Token", f"{state.settings.service_token[:8]}...")
    else:
        table.add_row("Status", "[yellow]Not authenticated[/yellow]")

    table.add_row("API URL", state.settings.api_url)

    state.console.print(table)
