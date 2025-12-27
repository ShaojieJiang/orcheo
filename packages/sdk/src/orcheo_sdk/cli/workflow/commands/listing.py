"""List workflows command."""

from __future__ import annotations
import typer
from orcheo_sdk.cli.output import format_datetime, render_table
from orcheo_sdk.cli.utils import load_with_cache
from orcheo_sdk.cli.workflow.app import _state, workflow_app
from orcheo_sdk.cli.workflow.inputs import _cache_notice
from orcheo_sdk.services import list_workflows_data


@workflow_app.command("list")
def list_workflows(
    ctx: typer.Context,
    archived: bool = typer.Option(
        False,
        "--archived",
        help="Include archived workflows in the list",
    ),
) -> None:
    """List workflows with metadata."""
    state = _state(ctx)
    payload, from_cache, stale = load_with_cache(
        state,
        f"workflows:archived:{archived}",
        lambda: list_workflows_data(state.client, archived=archived),
    )
    if from_cache:
        _cache_notice(state, "workflow catalog", stale)
    rows = []
    for item in payload:
        published_at = item.get("published_at")
        published_display = format_datetime(published_at) if published_at else "-"
        rows.append(
            [
                item.get("id"),
                item.get("name"),
                "Public" if item.get("is_public") else "Private",
                "yes" if item.get("require_login") else "no",
                "yes" if item.get("is_scheduled") else "no",
                published_display,
                item.get("share_url") or "-",
            ]
        )
    render_table(
        state.console,
        title="Workflows",
        columns=[
            "ID",
            "Name",
            "Visibility",
            "Require login",
            "Scheduled",
            "Published at",
            "Share URL",
        ],
        rows=rows,
        column_overflow={"ID": "fold", "Share URL": "fold"},
    )

    share_entries = []
    for workflow in payload:
        share_url = workflow.get("share_url")
        if not share_url:
            continue
        identifier = workflow.get("name") or workflow.get("id")
        share_entries.append(f"{identifier}: {share_url}")

    if share_entries:
        state.console.print()
        state.console.print("[bold]Share URLs[/bold]")
        for entry in share_entries:
            state.console.print(entry)


__all__ = ["list_workflows"]
