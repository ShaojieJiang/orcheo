"""Reference code generation commands."""

from __future__ import annotations
from typing import Annotated
import typer
from orcheo_sdk.cli.output import render_json
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.cli.utils import load_with_cache


code_app = typer.Typer(help="Generate workflow or node scaffolds.")

WorkflowIdArgument = Annotated[
    str,
    typer.Argument(help="Workflow identifier."),
]
ActorOption = Annotated[
    str,
    typer.Option("--actor", help="Actor used in the snippet."),
]


def _state(ctx: typer.Context) -> CLIState:
    return ctx.ensure_object(CLIState)


@code_app.command("scaffold")
def scaffold_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    actor: ActorOption = "cli",
) -> None:
    """Generate a Python snippet that triggers the workflow via the SDK."""
    state = _state(ctx)
    workflow, workflow_cached, workflow_stale = load_with_cache(
        state,
        f"workflow:{workflow_id}",
        lambda: state.client.get(f"/api/workflows/{workflow_id}"),
    )
    versions, versions_cached, versions_stale = load_with_cache(
        state,
        f"workflow:{workflow_id}:versions",
        lambda: state.client.get(f"/api/workflows/{workflow_id}/versions"),
    )
    if not versions:
        raise typer.BadParameter("Workflow has no versions to scaffold.")
    latest = max(versions, key=lambda entry: entry.get("version", 0))
    version_id = latest.get("id")
    if not version_id:
        raise typer.BadParameter("Latest workflow version is missing an id field.")

    snippet = f"""import os
from orcheo_sdk import HttpWorkflowExecutor, OrcheoClient

client = OrcheoClient(base_url=\"{state.client.base_url}\")
executor = HttpWorkflowExecutor(
    client,
    auth_token=os.environ.get(\"ORCHEO_SERVICE_TOKEN\"),
)

result = executor.trigger_run(
    \"{workflow_id}\",
    workflow_version_id=\"{version_id}\",
    triggered_by=\"{actor}\",
    inputs={{}},
)
print(result)
"""
    state.console.print(snippet)

    render_json(state.console, workflow, title="Workflow metadata")
    if workflow_cached or versions_cached:
        note = "[yellow]Using cached data[/yellow] for workflow scaffold"
        if workflow_stale or versions_stale:
            note += " (older than TTL)"
        state.console.print(note)
