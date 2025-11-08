"""Publish management commands for workflows."""

from __future__ import annotations
from typing import Any
import typer
from orcheo_sdk.cli.errors import APICallError, CLIError
from orcheo_sdk.cli.workflow.app import (
    ForceOption,
    WorkflowIdArgument,
    _state,
    workflow_app,
)
from orcheo_sdk.services import (
    publish_workflow_data,
    rotate_publish_token_data,
    unpublish_workflow_data,
)


def _raise_publish_error(workflow_id: str, exc: APICallError) -> None:
    """Convert common publish errors into actionable CLI messages."""
    if exc.status_code == 404:
        raise CLIError(
            f"Workflow '{workflow_id}' was not found. Run 'orcheo workflow list' to verify the ID."
        ) from exc
    if exc.status_code == 403:
        raise CLIError(
            "You do not have permission to manage publish state for this workflow. "
            "Ensure your service token includes workflow management privileges."
        ) from exc
    if exc.status_code == 409:
        raise CLIError(
            f"{exc}. If the workflow is already public, try 'orcheo workflow rotate-token {workflow_id}'."
        ) from exc
    raise exc


def _update_workflow_cache(state: Any, workflow_id: str, workflow: dict[str, Any]) -> None:
    """Store refreshed workflow metadata and invalidate related cache entries."""
    state.cache.store(f"workflow:{workflow_id}", workflow)
    state.cache.invalidate(f"workflow:{workflow_id}:versions")
    state.cache.invalidate(f"workflow:{workflow_id}:runs")
    state.cache.invalidate("workflows:archived:False")
    state.cache.invalidate("workflows:archived:True")


def _require_online(state: Any, action: str) -> None:
    if state.settings.offline:
        raise CLIError(f"{action} requires network connectivity.")


def _workflow_name(workflow: dict[str, Any], fallback: str) -> str:
    name = workflow.get("name")
    return str(name) if name else fallback


@workflow_app.command("publish")
def publish_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    require_login: bool = typer.Option(
        False,
        "--require-login",
        help="Require OAuth login for published workflow visitors.",
        is_flag=True,
    ),
    force: ForceOption = False,
) -> None:
    """Publish a workflow and display its share details."""
    state = _state(ctx)
    _require_online(state, "Publishing workflows")

    if not force:
        state.console.print("[bold]Publishing workflow[/bold]")
        state.console.print(
            "This action creates a shareable link for the workflow's ChatKit experience."
        )
        if require_login:
            state.console.print(
                "Visitors must authenticate before chatting when the link is shared."
            )
        else:
            state.console.print(
                "Anyone with the link can chat without logging in. Use --require-login to enforce OAuth."
            )
        typer.confirm("Proceed with publishing?", abort=True)

    try:
        response = publish_workflow_data(
            state.client,
            workflow_id,
            require_login=require_login,
            canvas_base_url=state.settings.canvas_base_url,
        )
    except APICallError as exc:  # pragma: no cover - exercised in tests
        _raise_publish_error(workflow_id, exc)
        return

    workflow = response.get("workflow", {})
    _update_workflow_cache(state, workflow_id, workflow)

    share_url = response.get("share_url") or workflow.get("share_url")
    publish_token = response.get("publish_token")
    message = response.get("message")
    name = _workflow_name(workflow, workflow_id)

    state.console.print(
        f"[green]Workflow '{name}' published successfully.[/green]"
    )
    state.console.print(
        f"Require login: {'yes' if workflow.get('require_login') else 'no'}"
    )
    if share_url:
        state.console.print(f"Share URL: {share_url}")
    else:
        state.console.print(
            "[yellow]Set ORCHEO_CANVAS_BASE_URL to display share links in CLI output.[/yellow]"
        )
    if publish_token:
        state.console.print(f"Publish token: {publish_token}")
    if message:
        state.console.print(message)


@workflow_app.command("rotate-token")
def rotate_publish_token(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    force: ForceOption = False,
) -> None:
    """Rotate a workflow's publish token."""
    state = _state(ctx)
    _require_online(state, "Rotating publish tokens")

    if not force:
        state.console.print(
            "Rotating the token invalidates the previous one for new chat sessions."
        )
        typer.confirm("Rotate the publish token now?", abort=True)

    try:
        response = rotate_publish_token_data(
            state.client,
            workflow_id,
            canvas_base_url=state.settings.canvas_base_url,
        )
    except APICallError as exc:  # pragma: no cover - exercised in tests
        _raise_publish_error(workflow_id, exc)
        return

    workflow = response.get("workflow", {})
    _update_workflow_cache(state, workflow_id, workflow)

    share_url = response.get("share_url") or workflow.get("share_url")
    publish_token = response.get("publish_token")
    message = response.get("message")
    name = _workflow_name(workflow, workflow_id)

    state.console.print(
        f"[green]Publish token for '{name}' rotated successfully.[/green]"
    )
    if share_url:
        state.console.print(f"Share URL: {share_url}")
    if publish_token:
        state.console.print(f"New publish token: {publish_token}")
    state.console.print(
        "Existing chat sessions may continue until they disconnect, but new sessions must use the new token."
    )
    if message:
        state.console.print(message)


@workflow_app.command("unpublish")
def unpublish_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    force: ForceOption = False,
) -> None:
    """Revoke public access to a workflow."""
    state = _state(ctx)
    _require_online(state, "Unpublishing workflows")

    if not force:
        state.console.print(
            "Unpublishing immediately disables the public chat link and invalidates publish tokens."
        )
        typer.confirm("Unpublish this workflow?", abort=True)

    try:
        response = unpublish_workflow_data(
            state.client,
            workflow_id,
            canvas_base_url=state.settings.canvas_base_url,
        )
    except APICallError as exc:  # pragma: no cover - exercised in tests
        _raise_publish_error(workflow_id, exc)
        return

    workflow = response.get("workflow", {})
    _update_workflow_cache(state, workflow_id, workflow)

    name = _workflow_name(workflow, workflow_id)
    state.console.print(
        f"[green]Workflow '{name}' is now private.[/green]"
    )
    state.console.print(
        "Publish a new token in the future to share the workflow again."
    )


__all__ = [
    "publish_workflow",
    "rotate_publish_token",
    "unpublish_workflow",
]
