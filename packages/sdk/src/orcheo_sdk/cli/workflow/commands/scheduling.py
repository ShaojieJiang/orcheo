"""Cron scheduling commands for workflows."""

from __future__ import annotations
import typer
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.output import print_json, render_json
from orcheo_sdk.cli.workflow.app import WorkflowIdArgument, _state, workflow_app
from orcheo_sdk.services import schedule_workflow_cron, unschedule_workflow_cron


@workflow_app.command("schedule")
def schedule_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
) -> None:
    """Schedule workflow execution based on its cron trigger."""
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Scheduling workflows requires network connectivity.")

    result = schedule_workflow_cron(state.client, workflow_id)
    if not state.human:
        print_json(result)
        return
    status = result.get("status")
    if status == "noop":
        state.console.print(f"[yellow]{result['message']}[/yellow]")
        return

    state.console.print(f"[green]{result['message']}[/green]")
    render_json(state.console, result.get("config", {}), title="Cron trigger")


@workflow_app.command("unschedule")
def unschedule_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
) -> None:
    """Disable cron-based workflow execution."""
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Unscheduling workflows requires network connectivity.")

    result = unschedule_workflow_cron(state.client, workflow_id)
    if not state.human:
        print_json(result)
        return
    state.console.print(f"[green]{result['message']}[/green]")


__all__ = ["schedule_workflow", "unschedule_workflow"]
