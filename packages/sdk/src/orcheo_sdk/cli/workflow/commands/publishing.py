"""Publish-related workflow commands."""

from __future__ import annotations
from collections.abc import Iterable
from typing import Any
import typer
from rich.console import Console
from orcheo_sdk.cli.cache import CacheManager
from orcheo_sdk.cli.config import CLISettings
from orcheo_sdk.cli.errors import APICallError, CLIError
from orcheo_sdk.cli.output import format_datetime
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


def _require_online(settings: CLISettings) -> None:
    """Ensure the command is not executed in offline mode."""
    if settings.offline:
        msg = "This command requires network connectivity."
        raise CLIError(msg)


def _apply_error_hints(workflow_id: str, exc: APICallError) -> APICallError:
    """Return a new ``APICallError`` instance with actionable guidance."""
    if exc.status_code == 404:
        message = (
            f"Workflow '{workflow_id}' was not found. "
            "Run 'orcheo workflow list' to review available workflows."
        )
        return APICallError(message, status_code=exc.status_code)
    if exc.status_code == 403:
        message = (
            f"Permission denied when modifying workflow '{workflow_id}'. "
            "Ensure your service token includes workflow:write access."
        )
        return APICallError(message, status_code=exc.status_code)
    return exc


def _visibility_label(workflow: dict[str, Any]) -> str:
    return "Public" if workflow.get("is_public") else "Private"


def _format_rotation_timestamp(workflow: dict[str, Any]) -> str:
    rotation = workflow.get("publish_token_rotated_at") or workflow.get("published_at")
    if not rotation:
        return "-"
    return format_datetime(rotation)


def _update_workflow_cache(cache: CacheManager, workflow: dict[str, Any]) -> None:
    """Refresh cached workflow entries after publish state changes."""
    workflow_id = str(workflow.get("id")) if workflow.get("id") else None
    if not workflow_id:
        return

    cache.store(f"workflow:{workflow_id}", workflow)

    def _update_collection(
        payload: Iterable[dict[str, Any]],
        *,
        archived_flag: bool,
    ) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        replaced = False
        for item in payload:
            if str(item.get("id")) == workflow_id:
                if bool(workflow.get("is_archived")) is archived_flag:
                    updated.append(workflow)
                replaced = True
            else:
                updated.append(item)
        if not replaced and bool(workflow.get("is_archived")) is archived_flag:
            updated.append(workflow)
        return updated

    for archived in (False, True):
        key = f"workflows:archived:{archived}"
        entry = cache.load(key)
        if entry is None:
            continue
        payload = entry.payload
        if isinstance(payload, list):
            cache.store(key, _update_collection(payload, archived_flag=archived))


def _print_publish_summary(
    console: Console,
    *,
    workflow: dict[str, Any],
    share_url: str | None,
    publish_token: str | None,
    message: str | None,
) -> None:
    """Render a human-friendly summary after publish actions."""
    console.print("[bold green]Workflow visibility updated successfully.[/bold green]")
    console.print(f"[bold]Status:[/] {_visibility_label(workflow)}")
    console.print(
        f"[bold]Require login:[/] {'Yes' if workflow.get('require_login') else 'No'}"
    )
    console.print(f"[bold]Last rotation:[/] {_format_rotation_timestamp(workflow)}")

    if share_url:
        console.print(f"[bold]Share URL:[/] {share_url}")
    else:
        console.print("[bold]Share URL:[/] -")
    if publish_token:
        console.print(
            f"[bold yellow]Publish token:[/] [reverse]{publish_token}[/reverse]"
        )
        console.print(
            "[dim]Store this token securely. It will not be shown again.[/dim]"
        )
    if message:
        console.print(f"\n[dim]{message}[/dim]")


@workflow_app.command("publish")
def publish_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    require_login: bool = typer.Option(
        False,
        "--require-login/--no-require-login",
        help="Require OAuth login for published chat access.",
        show_default=False,
    ),
    force: ForceOption = False,
) -> None:
    """Publish a workflow for ChatKit access."""
    state = _state(ctx)
    _require_online(state.settings)

    if not force:
        prompt = (
            f"Publish workflow '{workflow_id}' as public"
            f"{' (login required)' if require_login else ''}?"
        )
        typer.confirm(prompt, abort=True)

    try:
        result = publish_workflow_data(
            state.client,
            workflow_id,
            require_login=require_login,
            actor="cli",
        )
    except APICallError as exc:  # pragma: no cover - exercised in tests
        raise _apply_error_hints(workflow_id, exc) from exc

    workflow = result["workflow"]
    _update_workflow_cache(state.cache, workflow)

    _print_publish_summary(
        state.console,
        workflow=workflow,
        share_url=result.get("share_url"),
        publish_token=result.get("publish_token"),
        message=result.get("message"),
    )


@workflow_app.command("rotate-token")
def rotate_publish_token(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    force: ForceOption = False,
) -> None:
    """Rotate the publish token for a workflow."""
    state = _state(ctx)
    _require_online(state.settings)

    if not force:
        prompt = (
            f"Rotate the publish token for workflow '{workflow_id}'? "
            "Existing links will stop authorizing new sessions."
        )
        typer.confirm(prompt, abort=True)

    try:
        result = rotate_publish_token_data(
            state.client,
            workflow_id,
            actor="cli",
        )
    except APICallError as exc:  # pragma: no cover - exercised in tests
        raise _apply_error_hints(workflow_id, exc) from exc

    workflow = result["workflow"]
    _update_workflow_cache(state.cache, workflow)

    _print_publish_summary(
        state.console,
        workflow=workflow,
        share_url=result.get("share_url"),
        publish_token=result.get("publish_token"),
        message="Previous tokens can no longer start new chat sessions.",
    )


@workflow_app.command("unpublish")
def unpublish_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    force: ForceOption = False,
) -> None:
    """Revoke public ChatKit access for a workflow."""
    state = _state(ctx)
    _require_online(state.settings)

    if not force:
        prompt = f"Unpublish workflow '{workflow_id}'? This revokes public access."
        typer.confirm(prompt, abort=True)

    try:
        result = unpublish_workflow_data(
            state.client,
            workflow_id,
            actor="cli",
        )
    except APICallError as exc:  # pragma: no cover - exercised in tests
        raise _apply_error_hints(workflow_id, exc) from exc

    workflow = result["workflow"]
    _update_workflow_cache(state.cache, workflow)

    _print_publish_summary(
        state.console,
        workflow=workflow,
        share_url=None,
        publish_token=None,
        message="Workflow is now private to authenticated editors.",
    )


__all__ = [
    "publish_workflow",
    "rotate_publish_token",
    "unpublish_workflow",
]
