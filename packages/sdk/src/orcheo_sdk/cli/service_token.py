"""CLI commands for managing service tokens."""

from __future__ import annotations
from typing import Annotated
import typer
from rich.console import Console
from rich.table import Table
from orcheo_sdk.cli.config import require_config
from orcheo_sdk.cli.errors import handle_http_error
from orcheo_sdk.cli.http import http_client
from orcheo_sdk.cli.output import console_print, format_datetime, success, warning


app = typer.Typer(name="token", help="Manage service tokens for authentication")
console = Console()


@app.command("create")
def create_token(
    identifier: Annotated[
        str, typer.Option("--id", help="Optional identifier for the token")
    ] = None,
    scopes: Annotated[
        list[str],
        typer.Option(
            "--scope", "-s", help="Scopes to grant (can be specified multiple times)"
        ),
    ] = None,
    workspaces: Annotated[
        list[str],
        typer.Option(
            "--workspace",
            "-w",
            help="Workspace IDs the token can access (can be specified multiple times)",
        ),
    ] = None,
    expires_in: Annotated[
        int,
        typer.Option(
            "--expires-in",
            help="Expiration time in seconds (no expiration if omitted)",
            min=60,
        ),
    ] = None,
) -> None:
    """Create a new service token.

    The token secret is displayed once and cannot be retrieved later.
    Store it securely.
    """
    config = require_config()

    payload = {}
    if identifier:
        payload["identifier"] = identifier
    if scopes:
        payload["scopes"] = scopes
    if workspaces:
        payload["workspace_ids"] = workspaces
    if expires_in:
        payload["expires_in_seconds"] = expires_in

    with http_client(config) as client:
        try:
            response = client.post("/api/admin/service-tokens", json=payload)
            response.raise_for_status()
            data = response.json()

            console.print()
            console.print(
                "[bold green]Service token created successfully![/]",
                style="green",
            )
            console.print()
            console.print(f"[bold]ID:[/] {data['identifier']}")
            console.print(
                f"[bold yellow]Secret:[/] [reverse]{data['secret']}[/]",
                style="yellow",
            )
            console.print()
            warning("Store this secret securely. It will not be shown again.")
            console.print()

            if data.get("scopes"):
                console.print(f"[bold]Scopes:[/] {', '.join(data['scopes'])}")
            if data.get("workspace_ids"):
                console.print(
                    f"[bold]Workspaces:[/] {', '.join(data['workspace_ids'])}"
                )
            if data.get("expires_at"):
                console.print(
                    f"[bold]Expires:[/] {format_datetime(data['expires_at'])}"
                )

        except Exception as exc:
            handle_http_error(exc, "create service token")


@app.command("list")
def list_tokens() -> None:
    """List all service tokens."""
    config = require_config()

    with http_client(config) as client:
        try:
            response = client.get("/api/admin/service-tokens")
            response.raise_for_status()
            data = response.json()

            tokens = data.get("tokens", [])
            if not tokens:
                console_print("No service tokens found.")
                return

            table = Table(title=f"Service Tokens ({data['total']} total)")
            table.add_column("ID", style="cyan")
            table.add_column("Scopes", style="green")
            table.add_column("Workspaces", style="blue")
            table.add_column("Issued", style="dim")
            table.add_column("Expires", style="yellow")
            table.add_column("Status", style="magenta")

            for token in tokens:
                scopes_str = ", ".join(token.get("scopes", [])) or "-"
                workspaces_str = ", ".join(token.get("workspace_ids", [])) or "-"
                issued_str = (
                    format_datetime(token["issued_at"])
                    if token.get("issued_at")
                    else "-"
                )
                expires_str = (
                    format_datetime(token["expires_at"])
                    if token.get("expires_at")
                    else "Never"
                )

                if token.get("revoked_at"):
                    status = "[red]Revoked[/]"
                elif token.get("rotated_to"):
                    status = "[yellow]Rotated[/]"
                else:
                    status = "[green]Active[/]"

                table.add_row(
                    token["identifier"],
                    scopes_str,
                    workspaces_str,
                    issued_str,
                    expires_str,
                    status,
                )

            console.print(table)

        except Exception as exc:
            handle_http_error(exc, "list service tokens")


@app.command("show")
def show_token(token_id: str = typer.Argument(..., help="Token identifier")) -> None:
    """Show details for a specific service token."""
    config = require_config()

    with http_client(config) as client:
        try:
            response = client.get(f"/api/admin/service-tokens/{token_id}")
            response.raise_for_status()
            data = response.json()

            console.print()
            console.print(f"[bold]Service Token: {data['identifier']}[/]")
            console.print()

            table = Table(show_header=False, box=None)
            table.add_column("Field", style="bold")
            table.add_column("Value")

            table.add_row("ID", data["identifier"])

            if data.get("scopes"):
                table.add_row("Scopes", ", ".join(data["scopes"]))
            else:
                table.add_row("Scopes", "[dim]-[/]")

            if data.get("workspace_ids"):
                table.add_row("Workspaces", ", ".join(data["workspace_ids"]))
            else:
                table.add_row("Workspaces", "[dim]-[/]")

            if data.get("issued_at"):
                table.add_row("Issued", format_datetime(data["issued_at"]))

            if data.get("expires_at"):
                table.add_row("Expires", format_datetime(data["expires_at"]))
            else:
                table.add_row("Expires", "[dim]Never[/]")

            if data.get("revoked_at"):
                table.add_row(
                    "Revoked",
                    f"[red]{format_datetime(data['revoked_at'])}[/]",
                )
                if data.get("revocation_reason"):
                    table.add_row("Reason", data["revocation_reason"])

            if data.get("rotated_to"):
                table.add_row("Rotated To", data["rotated_to"])

            console.print(table)
            console.print()

        except Exception as exc:
            handle_http_error(exc, "show service token")


@app.command("rotate")
def rotate_token(
    token_id: str = typer.Argument(..., help="Token identifier to rotate"),
    overlap: int = typer.Option(
        300, "--overlap", help="Grace period in seconds where both tokens are valid"
    ),
    expires_in: int = typer.Option(
        None,
        "--expires-in",
        help="Expiration time for new token in seconds",
        min=60,
    ),
) -> None:
    """Rotate a service token, generating a new secret.

    The old token remains valid during the overlap period.
    """
    config = require_config()

    payload = {"overlap_seconds": overlap}
    if expires_in:
        payload["expires_in_seconds"] = expires_in

    with http_client(config) as client:
        try:
            response = client.post(
                f"/api/admin/service-tokens/{token_id}/rotate", json=payload
            )
            response.raise_for_status()
            data = response.json()

            console.print()
            console.print("[bold green]Token rotated successfully![/]", style="green")
            console.print()
            console.print(f"[bold]New Token ID:[/] {data['identifier']}")
            console.print(
                f"[bold yellow]New Secret:[/] [reverse]{data['secret']}[/]",
                style="yellow",
            )
            console.print()
            warning("Store this secret securely. It will not be shown again.")
            console.print()

            if data.get("message"):
                console.print(f"[dim]{data['message']}[/]")

        except Exception as exc:
            handle_http_error(exc, "rotate service token")


@app.command("revoke")
def revoke_token(
    token_id: str = typer.Argument(..., help="Token identifier to revoke"),
    reason: str = typer.Option(..., "--reason", "-r", help="Reason for revocation"),
) -> None:
    """Revoke a service token immediately."""
    config = require_config()

    with http_client(config) as client:
        try:
            response = client.delete(
                f"/api/admin/service-tokens/{token_id}", json={"reason": reason}
            )
            response.raise_for_status()

            success(f"Service token '{token_id}' revoked successfully")
            console.print(f"[dim]Reason: {reason}[/]")

        except Exception as exc:
            handle_http_error(exc, "revoke service token")


__all__ = ["app"]
