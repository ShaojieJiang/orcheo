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
        visibility = "public" if item.get("is_public") else "private"
        require_login = "yes" if item.get("require_login") else "no"
        rotated_at = item.get("publish_token_rotated_at") or item.get("published_at")
        rows.append(
            [
                item.get("id"),
                item.get("name"),
                item.get("slug"),
                "yes" if item.get("is_archived") else "no",
                visibility,
                require_login,
                format_datetime(rotated_at) if rotated_at else "—",
                item.get("share_url") or "—",
            ]
        )
    render_table(
        state.console,
        title="Workflows",
        columns=[
            "ID",
            "Name",
            "Slug",
            "Archived",
            "Visibility",
            "Require login",
            "Last rotated",
            "Share URL",
        ],
        rows=rows,
    )


__all__ = ["list_workflows"]
