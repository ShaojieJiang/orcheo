"""Credential management commands."""

from __future__ import annotations
import typer
from orcheo_sdk.cli import render as renderers
from orcheo_sdk.cli.runtime import CliError, CliRuntime, render_error
from orcheo_sdk.cli.services import (
    CredentialRecord,
    CredentialTemplateRecord,
    delete_credential,
    fetch_credential_templates,
    fetch_credentials,
    issue_credential,
)


credential_app = typer.Typer(help="Inspect and manage credential metadata")


def _runtime(ctx: typer.Context) -> CliRuntime:
    runtime = ctx.obj
    if not isinstance(runtime, CliRuntime):  # pragma: no cover
        raise typer.Exit(code=1)
    return runtime


def _resolve_template(
    templates: list[CredentialTemplateRecord],
    name_or_id: str,
) -> CredentialTemplateRecord:
    for template in templates:
        if template.id == name_or_id or template.name.lower() == name_or_id.lower():
            return template
    msg = f"Credential template '{name_or_id}' was not found"
    raise CliError(msg)


def _resolve_credential(
    credentials: list[CredentialRecord],
    candidate: str,
) -> CredentialRecord:
    for credential in credentials:
        if credential.id == candidate or credential.name.lower() == candidate.lower():
            return credential
    msg = f"Credential '{candidate}' was not found"
    raise CliError(msg)


@credential_app.command("list", help="List credentials visible to the caller")
def list_credentials(
    ctx: typer.Context,
    workflow_id: str | None = typer.Option(
        None,
        "--workflow-id",
        help="Scope results to a workflow",
    ),
) -> None:
    """Render a table of credentials returned by the API."""
    runtime = _runtime(ctx)
    if runtime.offline:
        render_error(runtime.console, "Listing credentials requires network access")
        raise typer.Exit(code=1)
    try:
        credentials = fetch_credentials(runtime, workflow_id=workflow_id)
    except CliError as exc:
        render_error(runtime.console, str(exc))
        raise typer.Exit(code=1) from exc
    renderers.render_credentials(runtime.console, credentials)


@credential_app.command("create", help="Issue a credential from a template")
def create_credential(
    ctx: typer.Context,
    template: str,
    name: str | None = typer.Option(
        None,
        "--name",
        help="Override credential name",
    ),
    secret: str | None = typer.Option(
        None,
        "--secret",
        help="Secret value for the credential (prompted if omitted)",
    ),
    scope: str | None = typer.Option(
        None,
        "--scope",
        help="Override template scopes (comma-separated values)",
    ),
    workflow_id: str | None = typer.Option(
        None,
        "--workflow-id",
        help="Scope results to a workflow",
    ),
    actor: str = typer.Option(
        "cli",
        "--actor",
        help="Actor recorded with the issuance",
    ),
) -> None:
    """Issue a credential from a stored template."""
    runtime = _runtime(ctx)
    if runtime.offline:
        render_error(runtime.console, "Creating credentials requires network access")
        raise typer.Exit(code=1)

    try:
        templates = fetch_credential_templates(runtime)
        selected = _resolve_template(templates, template)
    except CliError as exc:
        render_error(runtime.console, str(exc))
        raise typer.Exit(code=1) from exc

    secret_value = secret or typer.prompt(
        "Secret",
        hide_input=True,
        confirmation_prompt=True,
    )
    scopes = None
    if scope:
        scopes = [
            candidate.strip() for candidate in scope.split(",") if candidate.strip()
        ]

    try:
        response = issue_credential(
            runtime,
            template_id=selected.id,
            secret=secret_value,
            actor=actor,
            name=name,
            scopes=scopes,
            workflow_id=workflow_id,
        )
    except CliError as exc:
        render_error(runtime.console, str(exc))
        raise typer.Exit(code=1) from exc

    runtime.console.print("Credential issued successfully:")
    runtime.console.print(f"Credential ID: {response.get('credential_id')}")
    runtime.console.print(f"Name: {response.get('name', name or selected.name)}")
    runtime.console.print(f"Provider: {response.get('provider', selected.provider)}")


@credential_app.command("delete", help="Delete a credential entry")
def delete_credential_command(
    ctx: typer.Context,
    credential: str,
    workflow_id: str | None = typer.Option(
        None,
        "--workflow-id",
        help="Scope results to a workflow",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation",
        is_flag=True,
    ),
) -> None:
    """Delete a credential entry from the vault."""
    runtime = _runtime(ctx)
    if runtime.offline:
        render_error(runtime.console, "Deleting credentials requires network access")
        raise typer.Exit(code=1)

    if not yes:
        confirm = typer.confirm(f"Delete credential '{credential}'?", default=False)
        if not confirm:
            runtime.console.print("Aborted.")
            return

    try:
        delete_credential(runtime, credential, workflow_id=workflow_id)
    except CliError as exc:
        render_error(runtime.console, str(exc))
        raise typer.Exit(code=1) from exc

    runtime.console.print("Credential deleted.")


@credential_app.command("reference", help="Emit a [[credential]] reference snippet")
def credential_reference(
    ctx: typer.Context,
    credential: str,
    workflow_id: str | None = typer.Option(
        None,
        "--workflow-id",
        help="Scope results to a workflow",
    ),
) -> None:
    """Print the [[credential]] reference snippet for a credential."""
    runtime = _runtime(ctx)
    if runtime.offline:
        render_error(
            runtime.console,
            "Fetching credential references requires network access",
        )
        raise typer.Exit(code=1)

    try:
        credentials = fetch_credentials(runtime, workflow_id=workflow_id)
        selected = _resolve_credential(credentials, credential)
    except CliError as exc:
        render_error(runtime.console, str(exc))
        raise typer.Exit(code=1) from exc

    runtime.console.print(f"[[{selected.name}]]")
    runtime.console.print(
        (
            "Use this reference in workflow configurations to inject the "
            "credential at runtime."
        ),
    )
