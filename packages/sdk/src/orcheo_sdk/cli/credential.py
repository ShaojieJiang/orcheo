"""Credential management commands for the CLI."""

from __future__ import annotations
from typing import Annotated, Any
import typer
from orcheo_sdk.cli.output import render_json, render_table
from orcheo_sdk.cli.state import CLIState


credential_app = typer.Typer(help="Manage credentials stored in the Orcheo vault.")

WorkflowIdOption = Annotated[
    str | None,
    typer.Option("--workflow-id", help="Filter by workflow identifier."),
]
ScopeOption = Annotated[
    list[str] | None,
    typer.Option(
        "--scope",
        help="Optional list of scopes.",
        show_default=False,
    ),
]
KindOption = Annotated[
    str,
    typer.Option("--kind", help="Credential kind."),
]
CredentialNameArgument = Annotated[
    str,
    typer.Argument(help="Credential name."),
]
CredentialIdArgument = Annotated[
    str,
    typer.Argument(help="Credential identifier."),
]


def _state(ctx: typer.Context) -> CLIState:
    return ctx.ensure_object(CLIState)


@credential_app.command("list")
def list_credentials(
    ctx: typer.Context,
    workflow_id: WorkflowIdOption = None,
) -> None:
    """List credentials visible to the caller."""
    state = _state(ctx)
    params = {"workflow_id": workflow_id} if workflow_id else None
    credentials = state.client.get("/api/credentials", params=params)
    rows = [
        [
            item.get("id"),
            item.get("name"),
            item.get("provider"),
            item.get("status"),
            item.get("access"),
        ]
        for item in credentials
    ]
    render_table(
        state.console,
        title="Credentials",
        columns=["ID", "Name", "Provider", "Status", "Access"],
        rows=rows,
    )


@credential_app.command("create")
def create_credential(
    ctx: typer.Context,
    name: CredentialNameArgument,
    provider: Annotated[
        str, typer.Option("--provider", help="Credential provider identifier.")
    ],
    secret: Annotated[str, typer.Option("--secret", help="Credential secret value.")],
    actor: Annotated[
        str, typer.Option("--actor", help="Actor creating the credential.")
    ] = "cli",
    access: Annotated[
        str,
        typer.Option("--access", help="Access level: private/shared/public."),
    ] = "private",
    workflow_id: WorkflowIdOption = None,
    scopes: ScopeOption = None,
    kind: KindOption = "secret",
) -> None:
    """Create a credential via the vault API."""
    state = _state(ctx)
    payload: dict[str, Any] = {
        "name": name,
        "provider": provider,
        "secret": secret,
        "actor": actor,
        "access": access,
        "scopes": scopes or [],
        "kind": kind,
    }
    if workflow_id:
        payload["workflow_id"] = workflow_id
    response = state.client.post("/api/credentials", json_body=payload)
    render_json(state.console, response, title="Credential created")


@credential_app.command("delete")
def delete_credential(
    ctx: typer.Context,
    credential_id: CredentialIdArgument,
    workflow_id: WorkflowIdOption = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip confirmation prompt."),
    ] = False,
) -> None:
    """Delete a credential from the vault."""
    state = _state(ctx)
    if not force:
        typer.confirm(
            "Are you sure you want to delete this credential?",
            abort=True,
        )
    params = {"workflow_id": workflow_id} if workflow_id else None
    state.client.delete(f"/api/credentials/{credential_id}", params=params)
    state.console.print("Credential deleted.")


@credential_app.command("reference")
def credential_reference(
    ctx: typer.Context,
    name: CredentialNameArgument,
) -> None:
    """Print the credential reference string for use in nodes or workflows."""
    state = _state(ctx)
    reference = f"[[{name}]]"
    state.console.print(f"Use [bold]{reference}[/bold] in node configuration fields.")


@credential_app.command("update")
def update_credential(
    ctx: typer.Context,
    credential_id: CredentialIdArgument,
    secret: Annotated[
        str | None, typer.Option("--secret", help="New secret value.")
    ] = None,
    metadata: Annotated[
        str | None,
        typer.Option("--metadata", help="JSON payload with metadata overrides."),
    ] = None,
) -> None:
    """Update credential metadata when supported by the backend."""
    state = _state(ctx)
    state.console.print(
        "Credential updates are not yet supported by the backend API. "
        "Rotate credentials via templates or recreate them."
    )
    raise typer.Exit(code=0)
