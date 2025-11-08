"""Show workflow command."""

from __future__ import annotations
from collections.abc import Mapping
import typer
from orcheo_sdk.cli.output import format_datetime, render_json, render_table
from orcheo_sdk.cli.utils import load_with_cache
from orcheo_sdk.cli.workflow.app import WorkflowIdArgument, _state, workflow_app
from orcheo_sdk.cli.workflow.inputs import _cache_notice
from orcheo_sdk.cli.workflow.mermaid import _mermaid_from_graph
from orcheo_sdk.services import show_workflow_data


@workflow_app.command("show")
def show_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
) -> None:
    """Display details about a workflow, including its latest version and runs."""
    state = _state(ctx)
    workflow, workflow_cached, workflow_stale = load_with_cache(
        state,
        f"workflow:{workflow_id}",
        lambda: state.client.get(f"/api/workflows/{workflow_id}"),
    )
    if workflow_cached:
        _cache_notice(state, f"workflow {workflow_id}", workflow_stale)

    versions, _, _ = load_with_cache(
        state,
        f"workflow:{workflow_id}:versions",
        lambda: state.client.get(f"/api/workflows/{workflow_id}/versions"),
    )

    runs, runs_cached, runs_stale = load_with_cache(
        state,
        f"workflow:{workflow_id}:runs",
        lambda: state.client.get(f"/api/workflows/{workflow_id}/runs"),
    )
    if runs_cached:
        _cache_notice(state, f"workflow {workflow_id} runs", runs_stale)

    data = show_workflow_data(
        state.client,
        workflow_id,
        workflow=workflow,
        versions=versions,
        runs=runs,
    )

    workflow_details = data["workflow"]
    latest_version = data.get("latest_version")
    recent_runs = data.get("recent_runs", [])

    render_json(state.console, workflow_details, title="Workflow")

    publish_status = "public" if workflow_details.get("is_public") else "private"
    require_login = "yes" if workflow_details.get("require_login") else "no"
    state.console.print("\n[bold]Publish status[/bold]")
    state.console.print(f"Status: {publish_status}")
    state.console.print(f"OAuth login required: {require_login}")
    if workflow_details.get("published_at"):
        state.console.print(
            f"Published at: {format_datetime(str(workflow_details['published_at']))}"
        )
    if workflow_details.get("publish_token_rotated_at"):
        state.console.print(
            "Last rotated: "
            f"{format_datetime(str(workflow_details['publish_token_rotated_at']))}"
        )
    if workflow_details.get("share_url"):
        state.console.print(f"Share URL: {workflow_details['share_url']}")

    if latest_version:
        graph_raw = latest_version.get("graph", {})
        graph = graph_raw if isinstance(graph_raw, Mapping) else {}
        mermaid = _mermaid_from_graph(graph)
        state.console.print("\n[bold]Latest version[/bold]")
        render_json(state.console, latest_version)
        state.console.print("\n[bold]Mermaid[/bold]")
        state.console.print(mermaid)

    if recent_runs:
        rows = [
            [
                item.get("id"),
                item.get("status"),
                item.get("triggered_by"),
                item.get("created_at"),
            ]
            for item in recent_runs
        ]
        render_table(
            state.console,
            title="Recent runs",
            columns=["ID", "Status", "Actor", "Created at"],
            rows=rows,
        )


__all__ = ["show_workflow"]
