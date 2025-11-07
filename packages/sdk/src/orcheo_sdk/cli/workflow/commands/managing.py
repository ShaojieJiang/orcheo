"""Management commands for workflows."""

from __future__ import annotations
import typer
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.output import render_json
from orcheo_sdk.cli.utils import load_with_cache
from orcheo_sdk.cli.workflow.app import (
    EntrypointOption,
    FilePathArgument,
    ForceOption,
    FormatOption,
    OutputPathOption,
    WorkflowIdArgument,
    WorkflowIdOption,
    WorkflowNameOption,
    _state,
    workflow_app,
)
from orcheo_sdk.cli.workflow.inputs import _cache_notice, _validate_local_path
from orcheo_sdk.services import (
    delete_workflow_data,
    download_workflow_data,
    upload_workflow_data,
)


@workflow_app.command("delete")
def delete_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    force: ForceOption = False,
) -> None:
    """Delete a workflow by ID."""
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Deleting workflows requires network connectivity.")

    if not force:
        typer.confirm(
            f"Are you sure you want to delete workflow '{workflow_id}'?",
            abort=True,
        )

    result = delete_workflow_data(state.client, workflow_id)
    raw_message = result.get("message", "")
    if raw_message and "deleted successfully" in raw_message.lower():
        success_message = raw_message
    else:
        success_message = f"Workflow '{workflow_id}' deleted successfully."
    state.console.print(f"[green]{success_message}[/green]")


@workflow_app.command("upload")
def upload_workflow(
    ctx: typer.Context,
    file_path: FilePathArgument,
    workflow_id: WorkflowIdOption = None,
    entrypoint: EntrypointOption = None,
    workflow_name: WorkflowNameOption = None,
) -> None:
    """Upload a workflow from a Python or JSON file."""
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Uploading workflows requires network connectivity.")

    result = upload_workflow_data(
        state.client,
        file_path,
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        entrypoint=entrypoint,
        console=state.console,
    )
    identifier = workflow_id or result.get("id") or "workflow"
    action = "updated" if workflow_id else "uploaded"
    success_message = f"[green]Workflow '{identifier}' {action} successfully.[/green]"
    state.console.print(success_message)
    render_json(state.console, result, title="Workflow")


@workflow_app.command("download")
def download_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    output_path: OutputPathOption = None,
    format_type: FormatOption = "auto",
) -> None:
    """Download a workflow configuration to a file or stdout."""
    state = _state(ctx)
    payload, from_cache, stale = load_with_cache(
        state,
        f"workflow:{workflow_id}:download:{format_type}",
        lambda: download_workflow_data(
            state.client,
            workflow_id,
            output_path=None,
            format_type=format_type,
        ),
    )
    if from_cache:
        _cache_notice(state, f"workflow {workflow_id}", stale)

    content = payload["content"]

    if output_path:
        output_file = _validate_local_path(
            output_path,
            description="output",
            must_exist=False,
            require_file=True,
        )
        output_file.write_text(content, encoding="utf-8")
        state.console.print(f"[green]Workflow downloaded to '{output_path}'.[/green]")
    else:
        state.console.print(content)


__all__ = [
    "delete_workflow",
    "upload_workflow",
    "download_workflow",
]
