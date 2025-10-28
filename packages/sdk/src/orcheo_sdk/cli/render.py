"""Rendering helpers for CLI output."""

from __future__ import annotations
from collections.abc import Iterable
from datetime import datetime
from rich.console import Console
from rich.table import Table
from orcheo_sdk.cli.services import (
    CredentialRecord,
    NodeRecord,
    WorkflowDetail,
    WorkflowRunInfo,
    WorkflowSummary,
    WorkflowVersionInfo,
)


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.isoformat(timespec="seconds")


def render_node_table(console: Console, nodes: Iterable[NodeRecord]) -> None:
    """Render the node catalog in a Rich table."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("Name", no_wrap=True)
    table.add_column("Category", no_wrap=True)
    table.add_column("Description")
    table.add_column("Tags")
    for node in nodes:
        tags = ", ".join(sorted(node.tags)) if node.tags else "—"
        table.add_row(node.name, node.category, node.description, tags)
    console.print(table)


def render_workflow_table(
    console: Console,
    workflows: Iterable[WorkflowSummary],
) -> None:
    """Render workflow summaries in a table."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", no_wrap=True)
    table.add_column("Name")
    table.add_column("Tags")
    table.add_column("Archived", no_wrap=True)
    table.add_column("Updated")
    for workflow in workflows:
        tags = ", ".join(workflow.tags) if workflow.tags else "—"
        table.add_row(
            workflow.id,
            workflow.name,
            tags,
            "yes" if workflow.is_archived else "no",
            _format_datetime(workflow.updated_at),
        )
    console.print(table)


def render_workflow_detail(
    console: Console,
    detail: WorkflowDetail,
    *,
    latest_version: WorkflowVersionInfo | None,
    runs: Iterable[WorkflowRunInfo],
    mermaid: str | None = None,
    cache_warning: str | None = None,
) -> None:
    """Render detailed workflow information including Mermaid output."""
    console.print(f"Workflow: {detail.name} ({detail.id})")
    console.print(f"Slug: {detail.slug}")
    console.print(f"Description: {detail.description or '—'}")
    console.print(f"Tags: {', '.join(detail.tags) if detail.tags else '—'}")
    console.print(f"Archived: {'yes' if detail.is_archived else 'no'}")
    console.print(f"Created: {_format_datetime(detail.created_at)}")
    console.print(f"Updated: {_format_datetime(detail.updated_at)}")
    if cache_warning:
        console.print(f"Warning: {cache_warning}")
    console.print("")
    if latest_version is not None:
        console.print(
            "Latest version: "
            f"v{latest_version.version} ({_format_datetime(latest_version.created_at)})"
        )
        console.print(f"Notes: {latest_version.notes or '—'}")
    else:
        console.print("Latest version: —")
    console.print("")
    if mermaid:
        console.print("Mermaid diagram:")
        console.print("```mermaid")
        console.print(mermaid)
        console.print("```")
        console.print("")
    run_table = Table(show_header=True, header_style="bold")
    run_table.add_column("Run ID", no_wrap=True)
    run_table.add_column("Status", no_wrap=True)
    run_table.add_column("Triggered By", no_wrap=True)
    run_table.add_column("Created")
    run_table.add_column("Started")
    run_table.add_column("Completed")
    rows_added = False
    for run in runs:
        rows_added = True
        run_table.add_row(
            run.id,
            run.status,
            run.triggered_by,
            _format_datetime(run.created_at),
            _format_datetime(run.started_at),
            _format_datetime(run.completed_at),
        )
    if rows_added:
        console.print("Recent runs:")
        console.print(run_table)
    else:
        console.print("Recent runs: none available")


def render_credentials(
    console: Console,
    credentials: Iterable[CredentialRecord],
) -> None:
    """Render credential metadata in a table."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", no_wrap=True)
    table.add_column("Name")
    table.add_column("Provider", no_wrap=True)
    table.add_column("Access", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Kind", no_wrap=True)
    for credential in credentials:
        table.add_row(
            credential.id,
            credential.name,
            credential.provider,
            credential.access,
            credential.status,
            credential.kind,
        )
    console.print(table)
