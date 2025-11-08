"""CLI commands for workflow publish management."""

from __future__ import annotations
from typing import Any
import typer
from rich.console import Console
from rich.table import Table
from orcheo_sdk.cli.errors import APICallError, CLIError
from orcheo_sdk.cli.output import format_datetime
from orcheo_sdk.cli.workflow.app import (
    RequireLoginOption,
    WorkflowIdArgument,
    _state,
    workflow_app,
)
from orcheo_sdk.services import (
    publish_workflow_data,
    revoke_workflow_publish_data,
    rotate_publish_token_data,
)


def _print_publish_summary(
    console: Console,
    *,
    heading: str,
    publish_summary: dict[str, Any],
    publish_token: str | None,
    message: str | None,
) -> None:
    """Render a consistent publish summary block."""
    console.print(f"[bold]{heading}[/bold]")
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="bold")
    table.add_column("Value")

    status = publish_summary.get("status", "private")
    table.add_row("Status", status.capitalize())
    require_login = "Yes" if publish_summary.get("require_login") else "No"
    table.add_row("Require login", require_login)

    share_url = publish_summary.get("share_url")
    table.add_row("Share URL", share_url or "[dim]-[/]")

    published_at = publish_summary.get("published_at")
    table.add_row(
        "Published",
        format_datetime(published_at) if published_at else "[dim]-[/]",
    )

    rotated_at = publish_summary.get("publish_token_rotated_at")
    table.add_row(
        "Last rotated",
        format_datetime(rotated_at) if rotated_at else "[dim]-[/]",
    )

    published_by = publish_summary.get("published_by")
    table.add_row("Published by", published_by or "[dim]-[/]")

    console.print(table)

    if publish_token:
        console.print(
            "[bold yellow]Publish token:[/] [reverse]"
            f"{publish_token}"
            "[/]",
            style="yellow",
        )
        console.print(
            "[yellow]Store this token securely. It will not be shown again.[/yellow]",
        )

    if message:
        console.print(f"\n[dim]{message}[/dim]")


def _update_workflow_cache(state: Any, workflow: dict[str, Any]) -> None:
    """Persist the latest workflow snapshot in cache entries."""
    workflow_id = workflow.get("id")
    if not workflow_id:
        return

    state.cache.store(f"workflow:{workflow_id}", workflow)

    def _refresh_list_entry(cache_key: str) -> None:
        entry = state.cache.load(cache_key)
        if entry is None:
            return
        payload = entry.payload
        if not isinstance(payload, list):
            return
        updated = False
        for index, item in enumerate(payload):
            if isinstance(item, dict) and item.get("id") == workflow_id:
                payload[index] = workflow
                updated = True
        if updated:
            state.cache.store(cache_key, payload)

    for archived in (False, True):
        _refresh_list_entry(f"workflows:archived:{archived}")


def _handle_publish_error(exc: APICallError) -> None:
    """Raise a CLIError with actionable hints for known API failures."""
    if exc.status_code == 404:
        raise CLIError(
            f"{exc}. Run 'orcheo workflow list' to verify the workflow ID.",
        ) from exc
    if exc.status_code == 403:
        raise CLIError(
            f"{exc}. Ensure your service token has publish permissions.",
        ) from exc
    raise exc


@workflow_app.command("publish")
def publish_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    require_login: RequireLoginOption = False,
) -> None:
    """Publish a workflow for public ChatKit access."""
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Publishing workflows requires network connectivity.")

    prompt = (
        "Publishing makes the workflow accessible via share URL. Proceed?"
    )
    typer.confirm(prompt, abort=True)

    try:
        result = publish_workflow_data(
            state.client,
            workflow_id,
            require_login=require_login,
            actor="cli",
        )
    except APICallError as exc:  # pragma: no cover - handled via helper
        _handle_publish_error(exc)
        return

    _update_workflow_cache(state, result["workflow"])
    console = state.console
    console.print(
        f"[green]Workflow '{workflow_id}' published successfully.[/green]",
    )
    console.print()
    _print_publish_summary(
        console,
        heading="Publish details",
        publish_summary=result["publish_summary"],
        publish_token=result.get("publish_token"),
        message=result.get("message"),
    )


@workflow_app.command("rotate-token")
def rotate_publish_token(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
) -> None:
    """Rotate the publish token for an already published workflow."""
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Rotating publish tokens requires network connectivity.")

    typer.confirm(
        "Rotate the publish token? Existing links will require the new token.",
        abort=True,
    )

    try:
        result = rotate_publish_token_data(
            state.client,
            workflow_id,
            actor="cli",
        )
    except APICallError as exc:  # pragma: no cover - handled via helper
        _handle_publish_error(exc)
        return

    _update_workflow_cache(state, result["workflow"])
    console = state.console
    console.print(
        f"[green]Publish token rotated for workflow '{workflow_id}'.[/green]",
    )
    console.print(
        "[dim]Existing chats stay active, but new sessions must use the new "
        "token.[/dim]"
    )
    console.print()
    _print_publish_summary(
        console,
        heading="Updated publish details",
        publish_summary=result["publish_summary"],
        publish_token=result.get("publish_token"),
        message=result.get("message"),
    )


@workflow_app.command("unpublish")
def unpublish_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
) -> None:
    """Revoke public access to a workflow."""
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Unpublishing workflows requires network connectivity.")

    typer.confirm(
        "Unpublish the workflow? Existing share links will stop working.",
        abort=True,
    )

    try:
        result = revoke_workflow_publish_data(
            state.client,
            workflow_id,
            actor="cli",
        )
    except APICallError as exc:  # pragma: no cover - handled via helper
        _handle_publish_error(exc)
        return

    _update_workflow_cache(state, result["workflow"])
    console = state.console
    console.print(
        f"[green]Workflow '{workflow_id}' is no longer public.[/green]",
    )
    console.print()
    _print_publish_summary(
        console,
        heading="Current publish status",
        publish_summary=result["publish_summary"],
        publish_token=None,
        message=None,
    )


__all__ = [
    "publish_workflow",
    "rotate_publish_token",
    "unpublish_workflow",
]
