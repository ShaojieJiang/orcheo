"""Workflow management commands."""

from __future__ import annotations
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any
import typer
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.output import render_json, render_table
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.cli.utils import load_with_cache
from orcheo_sdk.client import HttpWorkflowExecutor, OrcheoClient


workflow_app = typer.Typer(help="Inspect and operate on workflows.")

WorkflowIdArgument = Annotated[
    str,
    typer.Argument(help="Workflow identifier."),
]
ActorOption = Annotated[
    str,
    typer.Option("--actor", help="Actor triggering the run."),
]
InputsOption = Annotated[
    str | None,
    typer.Option("--inputs", help="JSON inputs payload."),
]
InputsFileOption = Annotated[
    str | None,
    typer.Option("--inputs-file", help="Path to JSON file with inputs."),
]


def _state(ctx: typer.Context) -> CLIState:
    return ctx.ensure_object(CLIState)


def _mermaid_from_graph(graph: Mapping[str, Any]) -> str:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    lines = ["graph TD"]

    def _node_repr(node: Any) -> tuple[str, str]:
        if isinstance(node, Mapping):
            identifier = str(
                node.get("id")
                or node.get("name")
                or node.get("label")
                or node.get("type")
            )
            label = str(node.get("label") or node.get("type") or identifier)
        else:
            identifier = str(node)
            label = identifier
        safe_identifier = identifier.replace("-", "_")
        return safe_identifier, label

    for node in nodes:
        node_id, label = _node_repr(node)
        lines.append(f"    {node_id}[{label}]")

    for edge in edges:
        if isinstance(edge, Mapping):
            source = edge.get("from") or edge.get("source")
            target = edge.get("to") or edge.get("target")
        elif isinstance(edge, list | tuple) and len(edge) == 2:
            source, target = edge
        else:
            continue
        if not source or not target:
            continue
        source_id = str(source).replace("-", "_")
        target_id = str(target).replace("-", "_")
        lines.append(f"    {source_id} --> {target_id}")
    return "\n".join(lines)


@workflow_app.command("list")
def list_workflows(ctx: typer.Context) -> None:
    """List workflows with metadata."""
    state = _state(ctx)
    payload, from_cache, stale = load_with_cache(
        state,
        "workflows",
        lambda: state.client.get("/api/workflows"),
    )
    if from_cache:
        _cache_notice(state, "workflow catalog", stale)
    rows = []
    for item in payload:
        rows.append(
            [
                item.get("id"),
                item.get("name"),
                item.get("slug"),
                "yes" if item.get("is_archived") else "no",
            ]
        )
    render_table(
        state.console,
        title="Workflows",
        columns=["ID", "Name", "Slug", "Archived"],
        rows=rows,
    )


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

    versions, versions_cached, versions_stale = load_with_cache(
        state,
        f"workflow:{workflow_id}:versions",
        lambda: state.client.get(f"/api/workflows/{workflow_id}/versions"),
    )
    latest_version = max(
        versions,
        key=lambda entry: entry.get("version", 0),
        default=None,
    )

    runs, runs_cached, runs_stale = load_with_cache(
        state,
        f"workflow:{workflow_id}:runs",
        lambda: state.client.get(f"/api/workflows/{workflow_id}/runs"),
    )
    if runs_cached:
        _cache_notice(state, f"workflow {workflow_id} runs", runs_stale)

    render_json(state.console, workflow, title="Workflow")

    if latest_version:
        graph = latest_version.get("graph", {})
        mermaid = _mermaid_from_graph(graph)
        state.console.print("\n[bold]Latest version[/bold]")
        render_json(state.console, latest_version)
        state.console.print("\n[bold]Mermaid[/bold]")
        state.console.print(mermaid)

    if runs:
        recent = sorted(
            runs,
            key=lambda item: item.get("created_at", ""),
            reverse=True,
        )[:5]
        rows = [
            [
                item.get("id"),
                item.get("status"),
                item.get("triggered_by"),
                item.get("created_at"),
            ]
            for item in recent
        ]
        render_table(
            state.console,
            title="Recent runs",
            columns=["ID", "Status", "Actor", "Created at"],
            rows=rows,
        )


@workflow_app.command("run")
def run_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    triggered_by: ActorOption = "cli",
    inputs: InputsOption = None,
    inputs_file: InputsFileOption = None,
) -> None:
    """Trigger a workflow run using the latest version."""
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Workflow executions require network connectivity.")
    versions = state.client.get(f"/api/workflows/{workflow_id}/versions")
    if not versions:
        raise CLIError("Workflow has no versions to execute.")
    latest_version = max(versions, key=lambda entry: entry.get("version", 0))
    version_id = latest_version.get("id")
    if not version_id:
        raise CLIError("Latest workflow version is missing an id field.")

    payload_inputs: Mapping[str, Any] = {}
    if inputs and inputs_file:
        raise CLIError("Provide either --inputs or --inputs-file, not both.")
    if inputs:
        payload_inputs = _load_inputs_from_string(inputs)
    elif inputs_file:
        payload_inputs = _load_inputs_from_path(inputs_file)

    orcheo_client = OrcheoClient(base_url=state.client.base_url)
    executor = HttpWorkflowExecutor(
        orcheo_client,
        auth_token=state.settings.service_token,
        timeout=30.0,
    )
    result = executor.trigger_run(
        workflow_id,
        workflow_version_id=version_id,
        triggered_by=triggered_by,
        inputs=payload_inputs,
    )
    render_json(state.console, result, title="Run created")


def _load_inputs_from_string(value: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:  # pragma: no cover - handled via CLIError
        raise CLIError(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, Mapping):
        msg = "Inputs payload must be a JSON object."
        raise CLIError(msg)
    return payload


def _load_inputs_from_path(path: str) -> Mapping[str, Any]:
    path_obj = Path(path).expanduser()
    if not path_obj.exists():
        raise CLIError(f"Inputs file '{path}' does not exist.")
    if not path_obj.is_file():
        raise CLIError(f"Inputs path '{path}' is not a file.")
    data = json.loads(path_obj.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise CLIError("Inputs payload must be a JSON object.")
    return data


def _cache_notice(state: CLIState, subject: str, stale: bool) -> None:
    note = "[yellow]Using cached data[/yellow]"
    if stale:
        note += " (older than TTL)"
    state.console.print(f"{note} for {subject}.")
