"""Workflow listener control CLI commands."""

from __future__ import annotations
import typer
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.output import print_json, render_json
from orcheo_sdk.cli.workflow.app import (
    ActorOption,
    WorkflowIdArgument,
    _state,
    listeners_app,
)
from orcheo_sdk.services import (
    pause_workflow_listener_data,
    resume_workflow_listener_data,
)


ListenerSubscriptionIdArgument = typer.Argument(
    ...,
    help="Listener subscription identifier.",
)


@listeners_app.command("pause")
def pause_workflow_listener(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    subscription_id: str = ListenerSubscriptionIdArgument,
    actor: ActorOption = "cli",
) -> None:
    """Pause one workflow listener subscription."""
    _update_workflow_listener_status(
        ctx,
        workflow_id,
        subscription_id,
        actor=actor,
        action="pause",
    )


@listeners_app.command("resume")
def resume_workflow_listener(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    subscription_id: str = ListenerSubscriptionIdArgument,
    actor: ActorOption = "cli",
) -> None:
    """Resume one workflow listener subscription."""
    _update_workflow_listener_status(
        ctx,
        workflow_id,
        subscription_id,
        actor=actor,
        action="resume",
    )


def _update_workflow_listener_status(
    ctx: typer.Context,
    workflow_id: str,
    subscription_id: str,
    *,
    actor: str,
    action: str,
) -> None:
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Listener control requires network connectivity.")

    if action == "pause":
        result = pause_workflow_listener_data(
            state.client,
            workflow_id,
            subscription_id,
            actor=actor,
        )
    else:
        result = resume_workflow_listener_data(
            state.client,
            workflow_id,
            subscription_id,
            actor=actor,
        )

    if not state.human:
        print_json(result)
        return

    state.console.print(
        f"[green]Listener '{subscription_id}' {action}d for workflow "
        f"'{workflow_id}'.[/green]"
    )
    render_json(state.console, result, title="Listener")


__all__ = [
    "pause_workflow_listener",
    "resume_workflow_listener",
]
