"""Credential management commands."""

from __future__ import annotations
from typing import Any
import typer
from rich.text import Text
from .api import ApiRequestError, OfflineCacheMissError
from .render import render_kv_section, render_table
from .utils import abort_with_error, get_context, show_cache_notice


credential_app = typer.Typer(help="Manage Orcheo credentials.")


@credential_app.command("list")
def list_credentials(
    ctx: typer.Context,
    workflow_id: str | None = typer.Option(
        None, help="Filter credentials scoped to a workflow ID."
    ),
) -> None:
    """List credentials visible to the caller."""
    context = get_context(ctx)
    params: dict[str, str] = {}
    if workflow_id:
        params["workflow_id"] = workflow_id

    try:
        result = context.client.get_json(
            "/credentials",
            params=params or None,
            offline=context.offline,
            description="credentials",
        )
    except OfflineCacheMissError as exc:
        context.console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except ApiRequestError as exc:
        abort_with_error(context, exc)

    entries = result.data if isinstance(result.data, list) else []
    rows: list[tuple[str, str, str, str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        rows.append(
            (
                str(entry.get("id", "")),
                str(entry.get("name", "")),
                str(entry.get("provider", "")),
                str(entry.get("access", "")),
                str(entry.get("status", "")),
            )
        )

    if not rows:
        context.console.print("[yellow]No credentials found.[/yellow]")
    else:
        render_table(
            context.console,
            title="Credentials",
            columns=("ID", "Name", "Provider", "Access", "Status"),
            rows=rows,
        )

    if result.from_cache:
        show_cache_notice(context, result.timestamp)


@credential_app.command("reference")
def credential_reference(
    ctx: typer.Context,
    credential: str = typer.Argument(..., help="Credential ID or name."),
) -> None:
    """Output the [[credential]] reference snippet."""
    context = get_context(ctx)
    try:
        result = context.client.get_json(
            "/credentials",
            offline=context.offline,
            description="credentials",
        )
    except OfflineCacheMissError as exc:
        context.console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except ApiRequestError as exc:
        abort_with_error(context, exc)

    entries = result.data if isinstance(result.data, list) else []
    match = _find_credential(entries, credential)
    if match is None:
        context.console.print(
            f"[red]Credential '{credential}' not found in the current scope.[/red]"
        )
        raise typer.Exit(code=1)

    name = str(match.get("name", credential))
    snippet = f"[[{name}]]"
    message = Text("Credential reference: ")
    message.append(snippet, style="bold")
    context.console.print(message)
    context.console.print(
        "Use this snippet in node configurations to reference the credential."
    )

    if result.from_cache:
        show_cache_notice(context, result.timestamp)


@credential_app.command("create")
def create_credential(
    ctx: typer.Context,
    name: str = typer.Option(..., prompt=True, help="Credential name."),
    provider: str = typer.Option(..., prompt=True, help="Provider identifier."),
    secret: str = typer.Option(..., prompt=True, hide_input=True, help="Secret value."),
    access: str = typer.Option(
        "private", help="Access level: private, shared, or public."
    ),
    scopes: str = typer.Option(
        "", help="Comma-separated scopes to associate with the credential."
    ),
    workflow_id: str | None = typer.Option(
        None, help="Associate credential with a workflow scope."
    ),
    actor: str = typer.Option("cli", help="Actor recorded for audit purposes."),
    kind: str = typer.Option("secret", help="Credential kind (secret, oauth, token)."),
) -> None:
    """Create a credential via the Orcheo API."""
    context = get_context(ctx)

    payload = {
        "name": name,
        "provider": provider,
        "secret": secret,
        "access": access,
        "scopes": _parse_scopes(scopes),
        "workflow_id": workflow_id,
        "actor": actor,
        "kind": kind,
    }

    try:
        result = context.client.post_json(
            "/credentials",
            json=payload,
            description="credential",
        )
    except ApiRequestError as exc:
        abort_with_error(context, exc)

    data = result.data if isinstance(result.data, dict) else {}
    render_kv_section(
        context.console,
        title="Credential Created",
        pairs=[
            ("ID", str(data.get("id", ""))),
            ("Name", str(data.get("name", name))),
            ("Provider", str(data.get("provider", provider))),
            ("Access", str(data.get("access", access))),
        ],
    )


@credential_app.command("delete")
def delete_credential(
    ctx: typer.Context,
    credential_id: str = typer.Argument(..., help="Credential identifier."),
    workflow_id: str | None = typer.Option(None, help="Workflow scope, if required."),
) -> None:
    """Delete a credential from the vault."""
    context = get_context(ctx)
    params: dict[str, str] = {}
    if workflow_id:
        params["workflow_id"] = workflow_id

    try:
        context.client.fetch_json(
            "DELETE",
            f"/credentials/{credential_id}",
            params=params or None,
            description="credential deletion",
        )
    except ApiRequestError as exc:
        abort_with_error(context, exc)
    context.console.print(
        f"[green]Credential {credential_id} deleted successfully.[/green]"
    )


def _find_credential(entries: list[Any], identifier: str) -> dict[str, Any] | None:
    for item in entries:
        if not isinstance(item, dict):
            continue
        if str(item.get("id")) == identifier:
            return item
        if str(item.get("name", "")).lower() == identifier.lower():
            return item
    return None


def _parse_scopes(raw: str) -> list[str]:
    return [scope.strip() for scope in raw.split(",") if scope.strip()]


__all__ = ["credential_app"]
