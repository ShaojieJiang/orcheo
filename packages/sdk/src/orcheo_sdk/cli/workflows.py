"""Workflow management commands."""

from __future__ import annotations
import json
from datetime import datetime
from typing import Any
import typer
from .api import ApiRequestError, OfflineCacheMissError
from .render import graph_to_mermaid, render_kv_section, render_mermaid, render_table
from .state import CLIContext
from .utils import abort_with_error, get_context, show_cache_notice


workflow_app = typer.Typer(help="Inspect and run workflows.")


@workflow_app.command("list")
def list_workflows(ctx: typer.Context) -> None:
    """List workflows registered with the Orcheo backend."""
    context = get_context(ctx)

    try:
        result = context.client.get_json(
            "/workflows", offline=context.offline, description="workflows"
        )
    except OfflineCacheMissError as exc:
        context.console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except ApiRequestError as exc:
        abort_with_error(context, exc)

    workflows = result.data if isinstance(result.data, list) else []
    rows: list[tuple[str, str, str, str]] = []
    for item in workflows:
        if not isinstance(item, dict):
            continue
        workflow_id = str(item.get("id", ""))
        name = str(item.get("name", ""))
        slug = str(item.get("slug", ""))
        updated_at = _format_datetime(item.get("updated_at"))
        rows.append((workflow_id, name, slug, updated_at))

    if not rows:
        context.console.print("[yellow]No workflows found.[/yellow]")
    else:
        render_table(
            context.console,
            title="Workflows",
            columns=("ID", "Name", "Slug", "Updated"),
            rows=rows,
        )

    if result.from_cache:
        show_cache_notice(context, result.timestamp)


@workflow_app.command("show")
def show_workflow(
    ctx: typer.Context,
    workflow_id: str = typer.Argument(..., help="Workflow identifier or slug."),
) -> None:
    """Display workflow metadata, versions, and recent runs."""
    context = get_context(ctx)

    try:
        workflow_result = context.client.get_json(
            f"/workflows/{workflow_id}",
            offline=context.offline,
            description="workflow",
        )
    except OfflineCacheMissError as exc:
        context.console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except ApiRequestError as exc:
        abort_with_error(context, exc)

    workflow = workflow_result.data if isinstance(workflow_result.data, dict) else {}
    tags_value = ""
    tags_raw = workflow.get("tags")
    if isinstance(tags_raw, list):
        tags_value = ", ".join(str(tag) for tag in tags_raw)

    metadata_pairs = [
        ("ID", str(workflow.get("id", workflow_id))),
        ("Name", str(workflow.get("name", ""))),
        ("Slug", str(workflow.get("slug", ""))),
        ("Description", str(workflow.get("description", ""))),
        ("Tags", tags_value),
        ("Updated", _format_datetime(workflow.get("updated_at"))),
    ]
    render_kv_section(context.console, title="Workflow", pairs=metadata_pairs)

    versions = _fetch_versions(context, workflow_id)
    if versions:
        rows = [
            (
                str(item.get("version", "")),
                str(item.get("id", "")),
                _format_datetime(item.get("created_at")),
                str(item.get("created_by", "")),
            )
            for item in versions
        ]
        render_table(
            context.console,
            title="Versions",
            columns=("Version", "Version ID", "Created", "Author"),
            rows=rows,
        )

        latest = max(
            (v for v in versions if isinstance(v, dict)),
            key=lambda item: int(item.get("version", 0) or 0),
            default=None,
        )
        if isinstance(latest, dict):
            graph = latest.get("graph")
            if isinstance(graph, dict):
                mermaid = graph_to_mermaid(graph)
                render_mermaid(context.console, title="Latest Graph", mermaid=mermaid)

    runs = _fetch_runs(context, workflow_id)
    if runs:
        rows = [
            (
                str(item.get("id", "")),
                str(item.get("status", "")),
                _format_datetime(item.get("created_at")),
                _format_datetime(item.get("completed_at")),
            )
            for item in runs[:5]
        ]
        render_table(
            context.console,
            title="Recent Runs",
            columns=("Run ID", "Status", "Created", "Completed"),
            rows=rows,
        )

    if workflow_result.from_cache:
        show_cache_notice(context, workflow_result.timestamp)


@workflow_app.command("run")
def run_workflow(
    ctx: typer.Context,
    workflow_id: str = typer.Argument(..., help="Workflow identifier."),
    version_id: str = typer.Option(
        None, "--version-id", help="Workflow version identifier to execute."
    ),
    actor: str = typer.Option("cli", help="Actor recorded for the run."),
    inputs: str = typer.Option("{}", help="JSON payload passed as workflow inputs."),
) -> None:
    """Trigger a workflow execution run."""
    context = get_context(ctx)

    try:
        parsed_inputs = json.loads(inputs)
        if not isinstance(parsed_inputs, dict):
            raise ValueError
    except ValueError:
        context.console.print("[red]Inputs must be a JSON object.[/red]")
        raise typer.Exit(code=1) from None

    selected_version = version_id
    if not selected_version:
        versions = _fetch_versions(context, workflow_id)
        if not versions:
            context.console.print(
                "[red]Unable to determine workflow version; specify --version-id.[/red]"
            )
            raise typer.Exit(code=1)
        latest = max(
            (v for v in versions if isinstance(v, dict)),
            key=lambda item: int(item.get("version", 0) or 0),
        )
        selected_version = str(latest.get("id"))

    payload = {
        "workflow_version_id": selected_version,
        "triggered_by": actor,
        "input_payload": parsed_inputs,
    }

    try:
        result = context.client.post_json(
            f"/workflows/{workflow_id}/runs",
            json=payload,
            description="workflow run",
        )
    except ApiRequestError as exc:
        abort_with_error(context, exc)

    data = result.data if isinstance(result.data, dict) else {}
    metadata_pairs = [
        ("Run ID", str(data.get("id", ""))),
        ("Status", str(data.get("status", ""))),
        ("Triggered By", str(data.get("triggered_by", actor))),
        ("Created", _format_datetime(data.get("created_at"))),
    ]
    render_kv_section(context.console, title="Run", pairs=metadata_pairs)


def _fetch_versions(context: CLIContext, workflow_id: str) -> list[dict[str, Any]]:
    try:
        result = context.client.get_json(
            f"/workflows/{workflow_id}/versions",
            offline=context.offline,
            description="workflow versions",
        )
    except OfflineCacheMissError:
        return []
    except ApiRequestError as exc:
        abort_with_error(context, exc)
    versions = result.data if isinstance(result.data, list) else []
    return [item for item in versions if isinstance(item, dict)]


def _fetch_runs(context: CLIContext, workflow_id: str) -> list[dict[str, Any]]:
    try:
        result = context.client.get_json(
            f"/workflows/{workflow_id}/runs",
            offline=context.offline,
            description="workflow runs",
        )
    except OfflineCacheMissError:
        return []
    except ApiRequestError:
        return []
    runs = result.data if isinstance(result.data, list) else []
    return [item for item in runs if isinstance(item, dict)]


def _format_datetime(value: Any) -> str:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.isoformat()
        except ValueError:  # pragma: no cover - defensive fallback
            return value
    if isinstance(value, datetime):
        return value.isoformat()
    return ""


__all__ = ["workflow_app"]
