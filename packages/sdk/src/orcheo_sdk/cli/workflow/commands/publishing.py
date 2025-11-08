"""Publish management commands for workflows."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any
import typer
from orcheo_sdk.cli.errors import APICallError, CLIError
from orcheo_sdk.cli.output import render_json
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.cli.workflow.app import (
    AutoConfirmOption,
    RequireLoginOption,
    WorkflowIdArgument,
    _state,
    workflow_app,
)
from orcheo_sdk.services import (
    publish_workflow_data,
    rotate_publish_token_data,
    unpublish_workflow_data,
)


def _publish_summary_lines(payload: Mapping[str, Any]) -> list[str]:
    workflow = payload.get("workflow", {})
    lines: list[str] = []
    status = "public" if workflow.get("is_public") else "private"
    require_login = "yes" if workflow.get("require_login") else "no"
    workflow_id = workflow.get("id", "")
    lines.append(f"Workflow '{workflow_id}' publish status: {status}.")
    lines.append(f"OAuth login required: {require_login}")
    share_url = payload.get("share_url") or workflow.get("share_url")
    if share_url:
        lines.append(f"Share URL: {share_url}")
    return lines


def _handle_api_error(error: APICallError, workflow_id: str) -> None:
    if error.status_code == 404:
        raise CLIError(
            f"Workflow '{workflow_id}' was not found. "
            "Run 'orcheo workflow list' to review available workflows.",
        ) from error
    raise error


def _confirm_action(message: str, *, auto_confirm: bool) -> None:
    if auto_confirm:
        return
    typer.confirm(message, default=True, abort=True)


def _update_cached_workflow(state: CLIState, workflow: Mapping[str, Any]) -> None:
    workflow_id = str(workflow.get("id", "")).strip()
    if not workflow_id:
        return
    state.cache.store(f"workflow:{workflow_id}", dict(workflow))
    for archived in (False, True):
        cache_key = f"workflows:archived:{archived}"
        entry = state.cache.load(cache_key)
        if entry is None:
            continue
        payload = entry.payload
        if not isinstance(payload, list):
            continue
        replaced = False
        updated: list[Any] = []
        for item in payload:
            if isinstance(item, Mapping) and str(item.get("id", "")) == workflow_id:
                updated.append(dict(workflow))
                replaced = True
            else:
                updated.append(item)
        if replaced:
            state.cache.store(cache_key, updated)


@workflow_app.command("publish")
def publish_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    require_login: RequireLoginOption = False,
    yes: AutoConfirmOption = False,
) -> None:
    """Publish a workflow for public ChatKit access."""
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Publishing workflows requires network connectivity.")

    _confirm_action(
        (
            "Publishing makes your workflow accessible to anyone with the share "
            "link. Continue?"
        ),
        auto_confirm=yes,
    )

    try:
        payload = publish_workflow_data(
            state.client,
            workflow_id,
            require_login=require_login,
            actor="cli",
        )
    except APICallError as error:
        _handle_api_error(error, workflow_id)
        raise

    _update_cached_workflow(state, payload["workflow"])
    for line in _publish_summary_lines(payload):
        state.console.print(f"[green]{line}[/green]")
    if payload.get("publish_token"):
        state.console.print(
            f"\n[yellow]Publish token:[/yellow] {payload['publish_token']}"
        )
        if payload.get("message"):
            state.console.print(payload["message"])
    render_json(state.console, payload["workflow"], title="Workflow")


@workflow_app.command("rotate-token")
def rotate_publish_token(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    yes: AutoConfirmOption = False,
) -> None:
    """Rotate the publish token for a workflow."""
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Rotating publish tokens requires network connectivity.")

    _confirm_action(
        (
            "Rotating the publish token invalidates the current share link "
            "for new sessions. Continue?"
        ),
        auto_confirm=yes,
    )

    try:
        payload = rotate_publish_token_data(state.client, workflow_id, actor="cli")
    except APICallError as error:
        _handle_api_error(error, workflow_id)
        raise

    _update_cached_workflow(state, payload["workflow"])
    for line in _publish_summary_lines(payload):
        state.console.print(f"[green]{line}[/green]")
    if payload.get("publish_token"):
        state.console.print(
            f"\n[yellow]New publish token:[/yellow] {payload['publish_token']}"
        )
        if payload.get("message"):
            state.console.print(payload["message"])
    render_json(state.console, payload["workflow"], title="Workflow")


@workflow_app.command("unpublish")
def unpublish_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    yes: AutoConfirmOption = False,
) -> None:
    """Revoke public access to a workflow."""
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Unpublishing workflows requires network connectivity.")

    _confirm_action(
        "Unpublishing immediately revokes access for new chat sessions. Continue?",
        auto_confirm=yes,
    )

    try:
        payload = unpublish_workflow_data(state.client, workflow_id, actor="cli")
    except APICallError as error:
        _handle_api_error(error, workflow_id)
        raise

    _update_cached_workflow(state, payload["workflow"])
    state.console.print(f"[green]Workflow '{workflow_id}' is no longer public.[/green]")
    render_json(state.console, payload["workflow"], title="Workflow")


__all__ = [
    "publish_workflow",
    "rotate_publish_token",
    "unpublish_workflow",
]
