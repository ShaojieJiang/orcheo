"""Show workflow command."""

from __future__ import annotations
from collections.abc import Mapping
import typer
from rich.table import Table
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

    publish_summary = workflow_details.get("publish_summary", {})

    if publish_summary:
        state.console.print("[bold]Publish status[/bold]")
        summary_table = Table(show_header=False, box=None)
        summary_table.add_column("Field", style="bold")
        summary_table.add_column("Value")
        summary_table.add_row(
            "Status", publish_summary.get("status", "private").capitalize()
        )
        summary_table.add_row(
            "Require login",
            "Yes" if publish_summary.get("require_login") else "No",
        )
        share_url = publish_summary.get("share_url")
        summary_table.add_row("Share URL", share_url or "[dim]-[/]")
        published_at = publish_summary.get("published_at")
        summary_table.add_row(
            "Published",
            format_datetime(published_at) if published_at else "[dim]-[/]",
        )
        rotated_at = publish_summary.get("publish_token_rotated_at")
        summary_table.add_row(
            "Last rotated",
            format_datetime(rotated_at) if rotated_at else "[dim]-[/]",
        )
        published_by = publish_summary.get("published_by")
        summary_table.add_row("Published by", published_by or "[dim]-[/]")
        state.console.print(summary_table)
        state.console.print()

    render_json(state.console, workflow_details, title="Workflow")

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
