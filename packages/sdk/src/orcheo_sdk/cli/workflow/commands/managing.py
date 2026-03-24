"""Management commands for workflows."""

from __future__ import annotations
import json
from typing import Any
import typer
from rich.markup import escape
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.output import print_json, render_json
from orcheo_sdk.cli.utils import load_with_cache
from orcheo_sdk.cli.workflow.app import (
    ActorOption,
    ChatKitPromptsFileOption,
    ChatKitPromptsOption,
    ConfigOutputPathOption,
    EntrypointOption,
    FilePathArgument,
    ForceOption,
    OutputPathOption,
    RunnableConfigFileOption,
    RunnableConfigOption,
    VersionOption,
    WorkflowIdArgument,
    WorkflowIdOption,
    WorkflowNameOption,
    _state,
    workflow_app,
)
from orcheo_sdk.cli.workflow.inputs import (
    _cache_notice,
    _resolve_chatkit_start_screen_prompts,
    _resolve_runnable_config,
    _validate_local_path,
)
from orcheo_sdk.cli.workflow.reminders import (
    attach_workflow_vault_reminder,
    describe_workflow_vault_reminder,
    fetch_workflow_vault_readiness,
)
from orcheo_sdk.services import (
    delete_workflow_data,
    download_workflow_data,
    save_workflow_runnable_config_data,
    sync_cron_schedule_if_changed,
    update_workflow_data,
    upload_workflow_data,
)


def _print_workflow_vault_reminder(
    console: Any,
    readiness: dict[str, object] | None,
) -> None:
    reminder = describe_workflow_vault_reminder(readiness)
    if reminder is None:
        return
    console.print(f"[dim]Vault reminder: {escape(reminder)}[/dim]")


def _resolve_download_paths(
    output_path: str | None,
    config_output_path: str | None,
) -> tuple[Any | None, Any | None]:
    """Resolve and validate workflow download output paths."""
    output_file = None
    if output_path:
        output_file = _validate_local_path(
            output_path,
            description="output",
            must_exist=False,
            require_file=True,
        )

    config_file = None
    if config_output_path:
        config_file = _validate_local_path(
            config_output_path,
            description="config output",
            must_exist=False,
            require_file=True,
        )

    if output_file and config_file and output_file == config_file:
        raise CLIError("Output path and config output path must be different.")
    return output_file, config_file


def _write_downloaded_runnable_config(
    payload: dict[str, Any],
    *,
    config_file: Any | None,
    config_output_path: str | None,
) -> bool:
    """Write stored runnable config to disk when requested and available."""
    if config_file is None:
        return False

    runnable_raw = payload.get("runnable_config")
    if not isinstance(runnable_raw, dict):
        return False

    try:
        config_file.write_text(
            f"{json.dumps(runnable_raw, indent=2)}\n",
            encoding="utf-8",
        )
    except OSError as exc:  # pragma: no cover - filesystem errors
        raise CLIError(
            f"Failed to write workflow config output to '{config_output_path}'."
        ) from exc
    return True


def _emit_machine_download_stdout(
    payload: dict[str, Any],
    *,
    config_output_path: str | None,
    config_written: bool,
) -> bool:
    """Emit machine-readable stdout download output when applicable."""
    if config_output_path is None:
        print_json(payload)
        return True

    machine_payload = dict(payload)
    machine_payload.pop("runnable_config", None)
    machine_payload["config_written"] = config_written
    machine_payload["config_path"] = str(config_output_path) if config_written else None
    print_json(machine_payload)
    return True


def _build_machine_download_file_result(
    *,
    output_path: str,
    config_output_path: str | None,
    config_written: bool,
) -> dict[str, object]:
    """Build machine-readable download result for file output mode."""
    response: dict[str, object] = {"status": "success", "path": str(output_path)}
    if config_output_path is not None:
        response["config_written"] = config_written
        response["config_path"] = str(config_output_path) if config_written else None
    return response


def _print_downloaded_config_notice(
    console: Any,
    *,
    config_output_path: str,
    config_written: bool,
) -> None:
    """Render the human-readable companion-config download notice."""
    if config_written:
        console.print(
            f"[green]Workflow config downloaded to '{config_output_path}'.[/green]"
        )
        return
    console.print(
        "[yellow]Workflow has no stored runnable config; "
        "skipped config download.[/yellow]"
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

    if not state.human and not force:
        print_json({"error": "Use --force to confirm deletion in machine mode."})
        raise typer.Exit(code=1)
    if not force:
        typer.confirm(
            f"Are you sure you want to delete workflow '{workflow_id}'?",
            abort=True,
        )

    result = delete_workflow_data(state.client, workflow_id)
    if not state.human:
        print_json(result)
        return
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
    config: RunnableConfigOption = None,
    config_file: RunnableConfigFileOption = None,
) -> None:
    """Upload a workflow from a Python script."""
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Uploading workflows requires network connectivity.")

    runnable_config = _resolve_runnable_config(config, config_file)
    result = upload_workflow_data(
        state.client,
        file_path,
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        entrypoint=entrypoint,
        runnable_config=runnable_config,
        console=state.console,
    )
    resolved_id = workflow_id or result.get("id")

    # Auto-update cron schedule if it was already registered and has changed.
    cron_sync: dict[str, str] | None = None
    if resolved_id:
        try:
            cron_sync = sync_cron_schedule_if_changed(state.client, resolved_id)
        except Exception:  # noqa: BLE001
            cron_sync = None
    readiness = fetch_workflow_vault_readiness(state.client, resolved_id)

    if not state.human:
        if cron_sync and cron_sync.get("status") == "updated":
            result["cron_schedule"] = cron_sync
        print_json(attach_workflow_vault_reminder(result, readiness))
        return
    identifier = resolved_id or "workflow"
    action = "updated" if workflow_id else "uploaded"
    success_message = f"[green]Workflow '{identifier}' {action} successfully.[/green]"
    state.console.print(success_message)
    render_json(state.console, result, title="Workflow")
    if cron_sync and cron_sync.get("status") == "updated":
        state.console.print(f"[green]{cron_sync['message']}[/green]")
        render_json(state.console, cron_sync.get("config", {}), title="Cron trigger")
    _print_workflow_vault_reminder(state.console, readiness)


@workflow_app.command("update")
def update_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    workflow_name: WorkflowNameOption = None,
    handle: str | None = typer.Option(
        None,
        "--handle",
        help="Update the workflow handle.",
    ),
    description: str | None = typer.Option(
        None,
        "--description",
        help="Update the workflow description.",
    ),
    chatkit_prompts: ChatKitPromptsOption = None,
    chatkit_prompts_file: ChatKitPromptsFileOption = None,
    clear_chatkit_prompts: bool = typer.Option(
        False,
        "--clear-chatkit-prompts",
        help="Reset ChatKit start-screen prompts to the built-in defaults.",
    ),
    actor: ActorOption = "cli",
) -> None:
    """Update workflow metadata."""
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Updating workflows requires network connectivity.")
    if clear_chatkit_prompts and (
        chatkit_prompts is not None or chatkit_prompts_file is not None
    ):
        raise CLIError(
            "Use either --clear-chatkit-prompts or "
            "--chatkit-prompts/--chatkit-prompts-file, not both."
        )

    resolved_chatkit_prompts = _resolve_chatkit_start_screen_prompts(
        chatkit_prompts,
        chatkit_prompts_file,
    )

    if (
        workflow_name is None
        and handle is None
        and description is None
        and resolved_chatkit_prompts is None
        and not clear_chatkit_prompts
    ):
        raise CLIError("Provide at least one field to update.")

    result = update_workflow_data(
        state.client,
        workflow_id,
        name=workflow_name,
        handle=handle,
        description=description,
        chatkit_start_screen_prompts=resolved_chatkit_prompts,
        clear_chatkit_start_screen_prompts=clear_chatkit_prompts,
        actor=actor,
    )
    if not state.human:
        print_json(result)
        return

    state.console.print(
        f"[green]Workflow '{workflow_id}' updated successfully.[/green]"
    )
    render_json(state.console, result, title="Workflow")


@workflow_app.command("save-config")
def save_workflow_config(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    config: RunnableConfigOption = None,
    config_file: RunnableConfigFileOption = None,
    version: VersionOption = None,
    actor: ActorOption = "cli",
    clear: bool = typer.Option(
        False,
        "--clear",
        help="Clear stored runnable config for the selected version.",
    ),
) -> None:
    """Persist runnable config on an existing workflow version."""
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Saving workflow config requires network connectivity.")
    if clear and (config is not None or config_file is not None):
        msg = "Use either --clear or --config/--config-file, not both."
        raise CLIError(msg)

    runnable_config = None if clear else _resolve_runnable_config(config, config_file)
    if not clear and runnable_config is None:
        msg = "Provide --config, --config-file, or --clear."
        raise CLIError(msg)

    result = save_workflow_runnable_config_data(
        state.client,
        workflow_id,
        runnable_config=runnable_config,
        actor=actor,
        version=version,
    )
    if not state.human:
        print_json(result)
        return

    state.console.print(
        "[green]Saved runnable config without creating a new version.[/green]"
    )
    render_json(state.console, result, title="Workflow Config")


@workflow_app.command("download")
def download_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    output_path: OutputPathOption = None,
    config_output_path: ConfigOutputPathOption = None,
    version: VersionOption = None,
) -> None:
    """Download a workflow configuration to a file or stdout."""
    state = _state(ctx)
    format_type = "python"
    version_suffix = f":{version}" if version else ""
    config_suffix = ":with-config" if config_output_path else ""
    payload, from_cache, stale = load_with_cache(
        state,
        f"workflow:{workflow_id}:download:{format_type}{version_suffix}{config_suffix}",
        lambda: download_workflow_data(
            state.client,
            workflow_id,
            output_path=None,
            format_type=format_type,
            target_version=version,
            include_runnable_config=config_output_path is not None,
        ),
    )
    if from_cache:
        _cache_notice(state, f"workflow {workflow_id}", stale)

    content = payload["content"]
    output_file, config_file = _resolve_download_paths(output_path, config_output_path)
    config_written = _write_downloaded_runnable_config(
        payload,
        config_file=config_file,
        config_output_path=config_output_path,
    )

    if (
        not state.human
        and output_path is None
        and _emit_machine_download_stdout(
            payload,
            config_output_path=config_output_path,
            config_written=config_written,
        )
    ):
        return

    if output_file:
        output_file.write_text(content, encoding="utf-8")
        if not state.human:
            print_json(
                _build_machine_download_file_result(
                    output_path=str(output_path),
                    config_output_path=config_output_path,
                    config_written=config_written,
                )
            )
            return
        state.console.print(f"[green]Workflow downloaded to '{output_path}'.[/green]")
    else:
        state.console.print(content)

    if config_output_path is None:
        return
    _print_downloaded_config_notice(
        state.console,
        config_output_path=config_output_path,
        config_written=config_written,
    )


__all__ = [
    "delete_workflow",
    "save_workflow_config",
    "update_workflow",
    "upload_workflow",
    "download_workflow",
]
