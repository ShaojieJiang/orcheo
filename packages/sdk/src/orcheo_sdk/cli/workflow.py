"""Workflow management commands."""

from __future__ import annotations
import json
from collections.abc import Mapping, Sequence
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
    return _compiled_mermaid(graph)


def _compiled_mermaid(graph: Mapping[str, Any]) -> str:
    from langgraph.graph import END, START, StateGraph

    nodes = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))

    node_names = _collect_node_names(nodes)
    normalised_edges = _collect_edges(edges, node_names)

    stub: StateGraph[Any] = StateGraph(dict)  # type: ignore[type-var]
    for name in sorted(node_names):
        stub.add_node(name, _identity_state)  # type: ignore[type-var]

    compiled_edges: list[tuple[Any, Any]] = []
    for source, target in normalised_edges:
        try:
            compiled_edges.append(
                (
                    _normalise_vertex(source, START, END),
                    _normalise_vertex(target, START, END),
                )
            )
        except ValueError:
            continue

    if not compiled_edges:
        if node_names:
            compiled_edges.append((START, sorted(node_names)[0]))
        else:
            compiled_edges.append((START, END))
    elif not any(source is START for source, _ in compiled_edges):
        targets = {target for _, target in compiled_edges}
        for candidate in sorted(node_names):
            if candidate not in targets:
                compiled_edges.append((START, candidate))
                break
        else:
            compiled_edges.append((START, compiled_edges[0][0]))

    for source, target in compiled_edges:
        stub.add_edge(source, target)

    compiled = stub.compile()
    return compiled.get_graph().draw_mermaid()


def _identity_state(state: dict[str, Any], *_: Any, **__: Any) -> dict[str, Any]:
    return state


def _collect_node_names(nodes: Sequence[Any]) -> set[str]:
    names: set[str] = set()
    for node in nodes:
        identifier = _node_identifier(node)
        if not identifier:
            continue
        if identifier.upper() in {"START", "END"}:
            continue
        names.add(identifier)
    return names


def _collect_edges(edges: Sequence[Any], node_names: set[str]) -> list[tuple[Any, Any]]:
    pairs: list[tuple[Any, Any]] = []
    for edge in edges:
        resolved = _resolve_edge(edge)
        if not resolved:
            continue
        source, target = resolved
        pairs.append((source, target))
        _register_endpoint(node_names, source)
        _register_endpoint(node_names, target)
    return pairs


def _node_identifier(node: Any) -> str | None:
    if isinstance(node, Mapping):
        raw = (
            node.get("id") or node.get("name") or node.get("label") or node.get("type")
        )
        if raw is None:
            return None
        return str(raw)
    if node is None:
        return None
    return str(node)


def _resolve_edge(edge: Any) -> tuple[Any, Any] | None:
    if isinstance(edge, Mapping):
        source = edge.get("from") or edge.get("source")
        target = edge.get("to") or edge.get("target")
    elif isinstance(edge, Sequence):
        if isinstance(edge, (str, bytes)):  # noqa: UP038 - tuple keeps runtime compatibility
            return None
        if len(edge) != 2:
            return None
        source, target = edge
    else:
        return None
    if not source or not target:
        return None
    return source, target


def _register_endpoint(node_names: set[str], endpoint: Any) -> None:
    text = str(endpoint)
    if text.upper() in {"START", "END"}:
        return
    node_names.add(text)


def _normalise_vertex(value: Any, start: Any, end: Any) -> Any:
    text = str(value)
    upper = text.upper()
    if upper == "START":
        return start
    if upper == "END":
        return end
    return text


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
