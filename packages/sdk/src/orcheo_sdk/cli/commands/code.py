"""Code generation helpers for the CLI."""

from __future__ import annotations
import typer
from orcheo_sdk.cli.commands.workflows import _select_version
from orcheo_sdk.cli.runtime import CliError, CliRuntime, render_error, render_warning
from orcheo_sdk.cli.services import fetch_workflow_detail


code_app = typer.Typer(help="Generate workflow reference snippets")


def _runtime(ctx: typer.Context) -> CliRuntime:
    runtime = ctx.obj
    if not isinstance(runtime, CliRuntime):  # pragma: no cover
        raise typer.Exit(code=1)
    return runtime


@code_app.command("scaffold", help="Generate a Python snippet for running a workflow")
def scaffold(
    ctx: typer.Context,
    workflow_id: str,
    version: int | None = typer.Option(
        None,
        "--version",
        help="Workflow version to target",
    ),
    actor: str = typer.Option(
        "cli",
        "--actor",
        help="Actor used in the snippet",
    ),
) -> None:
    """Emit a Python scaffold for triggering a workflow run."""
    runtime = _runtime(ctx)
    try:
        _detail, versions, cache_entry = fetch_workflow_detail(runtime, workflow_id)
    except CliError as exc:
        render_error(runtime.console, str(exc))
        raise typer.Exit(code=1) from exc

    try:
        selected_version = _select_version(versions, version)
    except CliError as exc:
        render_error(runtime.console, str(exc))
        raise typer.Exit(code=1) from exc

    if runtime.offline and cache_entry and runtime.cache.is_stale(cache_entry):
        render_warning(
            runtime.console,
            (
                "Workflow scaffold data is older than 24 hours; "
                "refresh online for the latest version."
            ),
        )

    api_url = runtime.settings.api_url
    snippet = [
        "import os",
        "",
        "from orcheo_sdk import HttpWorkflowExecutor, OrcheoClient",
        "",
        f'client = OrcheoClient(base_url="{api_url}")',
        (
            "executor = HttpWorkflowExecutor("
            'client, auth_token=os.getenv("ORCHEO_SERVICE_TOKEN"))'
        ),
        "response = executor.trigger_run(",
        f'    workflow_id="{workflow_id}",',
        f'    workflow_version_id="{selected_version.id}",',
        f'    triggered_by="{actor}",',
        "    inputs={},",
        ")",
        "print(response)",
    ]

    runtime.console.print("Python scaffold:")
    runtime.console.print("```python")
    for line in snippet:
        runtime.console.print(line)
    runtime.console.print("```")
