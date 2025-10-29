"""Workflow management commands."""

from __future__ import annotations
import json
import re
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
ForceOption = Annotated[
    bool,
    typer.Option("--force", help="Skip confirmation prompt."),
]
FilePathArgument = Annotated[
    str,
    typer.Argument(help="Path to workflow file (Python or JSON)."),
]
OutputPathOption = Annotated[
    str | None,
    typer.Option("--output", "-o", help="Output file path (default: stdout)."),
]
FormatOption = Annotated[
    str,
    typer.Option("--format", "-f", help="Output format (json or python)."),
]


def _state(ctx: typer.Context) -> CLIState:
    return ctx.ensure_object(CLIState)


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _generate_slug(value: str) -> str:
    normalized = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    fallback = value.strip().lower()
    return normalized or fallback or value


def _normalize_workflow_name(name: str | None) -> str | None:
    if name is None:
        return None
    normalized = name.strip()
    if not normalized:
        raise CLIError("Workflow name cannot be empty.")
    return normalized


def _upload_langgraph_script(
    state: CLIState,
    workflow_config: dict[str, Any],
    workflow_id: str | None,
    path: Path,
    name_override: str | None,
) -> dict[str, Any]:
    """Upload a LangGraph script using the ingestion API.

    This function handles the two-step process:
    1. Create/get workflow
    2. Ingest the script to create a version
    """
    script = workflow_config["script"]
    entrypoint = workflow_config.get("entrypoint")

    derived_name = path.stem.replace("_", "-")
    workflow_name = name_override or derived_name
    workflow_slug = _generate_slug(workflow_name) if name_override else derived_name

    if workflow_id:
        # Use existing workflow
        try:
            workflow = state.client.get(f"/api/workflows/{workflow_id}")
        except Exception as exc:
            raise CLIError(f"Failed to fetch workflow '{workflow_id}': {exc}") from exc
        if name_override and workflow.get("name") != name_override:
            try:
                state.client.post(
                    f"/api/workflows/{workflow_id}",
                    json_body={"name": name_override},
                )
                workflow["name"] = name_override
            except Exception as exc:
                raise CLIError(
                    f"Failed to rename workflow '{workflow_id}': {exc}"
                ) from exc
    else:
        # Create new workflow
        create_payload = {
            "name": workflow_name,
            "slug": workflow_slug,
            "description": f"LangGraph workflow from {path.name}",
            "tags": ["langgraph", "cli-upload"],
            "actor": "cli",
        }
        try:
            workflow = state.client.post("/api/workflows", json_body=create_payload)
            workflow_id = workflow["id"]
            state.console.print(
                f"[green]Created workflow '{workflow_id}' ({workflow_name})[/green]"
            )
        except Exception as exc:
            raise CLIError(f"Failed to create workflow: {exc}") from exc

    # Ingest the script to create a version
    ingest_payload = {
        "script": script,
        "entrypoint": entrypoint,
        "metadata": {"source": "cli-upload", "filename": path.name},
        "notes": f"Uploaded from {path.name} via CLI",
        "created_by": "cli",
    }

    try:
        version = state.client.post(
            f"/api/workflows/{workflow_id}/versions/ingest",
            json_body=ingest_payload,
        )
        state.console.print(
            f"[green]Ingested LangGraph script as version {version['version']}[/green]"
        )
    except Exception as exc:
        raise CLIError(f"Failed to ingest LangGraph script: {exc}") from exc

    # Return the workflow with the latest version info
    workflow["latest_version"] = version
    return workflow


async def _stream_workflow_run(
    state: CLIState,
    workflow_id: str,
    graph_config: dict[str, Any],
    inputs: Mapping[str, Any],
    *,
    triggered_by: str | None = None,
) -> str:
    """Stream workflow execution via WebSocket and display node outputs."""
    import json
    import uuid
    import websockets
    from websockets import exceptions as ws_exceptions

    # Build WebSocket URL and payload
    ws_base = state.client.base_url.replace("http://", "ws://").replace(
        "https://", "wss://"
    )
    websocket_url = f"{ws_base}/ws/workflow/{workflow_id}"
    execution_id = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "type": "run_workflow",
        "graph_config": graph_config,
        "inputs": dict(inputs),
        "execution_id": execution_id,
    }
    if triggered_by is not None:
        payload["triggered_by"] = triggered_by

    state.console.print("[cyan]Starting workflow execution...[/cyan]")
    state.console.print(f"[dim]Execution ID: {execution_id}[/dim]\n")

    try:
        async with websockets.connect(
            websocket_url, open_timeout=5, close_timeout=5
        ) as websocket:
            await websocket.send(json.dumps(payload))
            return await _process_stream_messages(state, websocket)
    except (ConnectionRefusedError, OSError) as exc:
        state.console.print(
            "[red]Failed to connect to server.[/red]\n"
            "[dim]Ensure the backend is running.[/dim]"
        )
        state.console.print(f"[dim]Error: {exc}[/dim]")
        return "connection_error"
    except TimeoutError:
        state.console.print(
            "[red]Timed out while connecting.[/red]\n"
            "[dim]Retry once the server is reachable.[/dim]"
        )
        return "timeout"
    except ws_exceptions.InvalidStatusCode as exc:  # type: ignore[attr-defined]
        state.console.print(
            f"[red]Server rejected connection (HTTP {exc.status_code}).[/red]\n"
            "[dim]Verify the workflow ID and backend availability.[/dim]"
        )
        return f"http_{exc.status_code}"
    except ws_exceptions.WebSocketException as exc:
        state.console.print(f"[red]WebSocket error: {exc}[/red]")
        return "websocket_error"


async def _process_stream_messages(state: CLIState, websocket: Any) -> str:
    """Process streaming messages from WebSocket."""
    import json

    async for message in websocket:
        update = json.loads(message)
        status = update.get("status")

        if status:
            final_status = _handle_status_update(state, update)
            if final_status:
                return final_status
            continue

        # Handle node execution events
        _handle_node_event(state, update)

    return "completed"


def _handle_status_update(state: CLIState, update: dict[str, Any]) -> str | None:
    """Handle status updates. Returns final status if workflow should end."""
    status = update.get("status")

    if status == "error":
        error_detail = update.get("error") or "Unknown error"
        state.console.print(f"[red]✗ Error: {error_detail}[/red]")
        return "error"
    if status == "cancelled":
        reason = update.get("reason") or "No reason provided"
        state.console.print(f"[yellow]⚠ Cancelled: {reason}[/yellow]")
        return "cancelled"
    if status == "completed":
        state.console.print("[green]✓ Workflow completed successfully[/green]")
        return "completed"

    state.console.print(f"[dim]Status: {status}[/dim]")
    return None


def _handle_node_event(state: CLIState, update: dict[str, Any]) -> None:
    """Handle node execution event updates."""
    node = update.get("node")
    event = update.get("event")
    payload_data = update.get("payload") or update.get("data")

    if not (node and event):
        return

    if event == "on_chain_start":
        state.console.print(f"[blue]→ {node}[/blue] [dim]starting...[/dim]")
    elif event == "on_chain_end":
        state.console.print(f"[green]✓ {node}[/green]")
        if payload_data:
            _render_node_output(state, payload_data)
    elif event == "on_chain_error":
        error_msg = payload_data.get("error") if payload_data else "Unknown"
        state.console.print(f"[red]✗ {node}[/red] [dim]{error_msg}[/dim]")
    else:
        # Other events - show in dim
        state.console.print(f"[dim][{event}] {node}: {payload_data}[/dim]")


def _render_node_output(state: CLIState, data: Any) -> None:
    """Render node output in a compact, readable format."""
    if not data:
        return

    if isinstance(data, dict):
        # Show key-value pairs inline for small dicts
        if len(data) <= 3 and all(
            isinstance(v, str | int | float | bool) for v in data.values()
        ):
            items = [f"{k}={v!r}" for k, v in data.items()]
            state.console.print(f"  [dim]{', '.join(items)}[/dim]")
        else:
            # Use JSON rendering for complex data
            render_json(state.console, data, title=None)
    elif isinstance(data, str) and len(data) < 100:
        state.console.print(f"  [dim]{data}[/dim]")
    else:
        # Fallback to JSON for other types
        import json as json_module

        try:
            formatted = json_module.dumps(data, indent=2, default=str)
            state.console.print(f"[dim]{formatted}[/dim]")
        except Exception:  # pragma: no cover
            state.console.print(f"  [dim]{data!r}[/dim]")


def _mermaid_from_graph(graph: Mapping[str, Any]) -> str:
    if isinstance(graph, Mapping):
        summary = graph.get("summary")
        if isinstance(summary, Mapping):
            return _compiled_mermaid(summary)
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
        except ValueError:  # pragma: no cover - handled via continue
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
def list_workflows(
    ctx: typer.Context,
    archived: bool = typer.Option(
        False,
        "--archived",
        help="Include archived workflows in the list",
    ),
) -> None:
    """List workflows with metadata.

    By default, only shows unarchived workflows.
    Use --archived to include archived workflows.
    """
    state = _state(ctx)
    url = "/api/workflows"
    if archived:
        url += "?include_archived=true"
    payload, from_cache, stale = load_with_cache(
        state,
        "workflows",
        lambda: state.client.get(url),
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
    stream: Annotated[
        bool,
        typer.Option(
            "--stream/--no-stream",
            help="Stream node outputs in real-time (default: True).",
        ),
    ] = True,
) -> None:
    """Trigger a workflow run using the latest version.

    By default, streams node outputs in real-time via WebSocket.
    Use --no-stream to trigger without streaming (returns run ID immediately).
    """
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
    graph_config = latest_version.get("graph")

    # Fall back to non-streaming if graph config is not available
    can_stream = stream and graph_config is not None

    payload_inputs: Mapping[str, Any] = {}
    if inputs and inputs_file:
        raise CLIError("Provide either --inputs or --inputs-file, not both.")
    if inputs:
        payload_inputs = _load_inputs_from_string(inputs)
    elif inputs_file:
        payload_inputs = _load_inputs_from_path(inputs_file)

    if can_stream:
        # Stream workflow execution via WebSocket
        import asyncio

        final_status = asyncio.run(
            _stream_workflow_run(
                state,
                workflow_id,
                graph_config,
                payload_inputs,
                triggered_by=triggered_by,
            )
        )
        if final_status in {"error", "cancelled", "connection_error", "timeout"}:
            raise CLIError(f"Workflow execution failed with status: {final_status}")
    else:
        # Non-streaming: just trigger and return run ID
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


@workflow_app.command("delete")
def delete_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    force: ForceOption = False,
) -> None:
    """Delete a workflow by ID."""
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Deleting workflows requires network connectivity.")

    if not force:
        typer.confirm(
            f"Are you sure you want to delete workflow '{workflow_id}'?",
            abort=True,
        )

    state.client.delete(f"/api/workflows/{workflow_id}")
    state.console.print(
        f"[green]Workflow '{workflow_id}' deleted successfully.[/green]"
    )


@workflow_app.command("upload")
def upload_workflow(
    ctx: typer.Context,
    file_path: FilePathArgument,
    workflow_id: Annotated[
        str | None,
        typer.Option("--id", help="Workflow ID (for updates). Creates new if omitted."),
    ] = None,
    entrypoint: Annotated[
        str | None,
        typer.Option(
            "--entrypoint",
            help=(
                "Entrypoint function/variable for LangGraph scripts "
                "(auto-detect if omitted)."
            ),
        ),
    ] = None,
    workflow_name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Rename the workflow when uploading.",
        ),
    ] = None,
) -> None:
    """Upload a workflow from a Python or JSON file.

    For Python files, supports two formats:
    1. SDK Workflow: File defines a 'workflow' variable with Workflow instance
    2. LangGraph script: Raw LangGraph code (auto-detected if no 'workflow' var)

    For JSON files, must contain valid workflow config with 'name' and 'graph'.

    Use --entrypoint to specify a custom entrypoint for LangGraph scripts.
    """
    state = _state(ctx)
    if state.settings.offline:
        raise CLIError("Uploading workflows requires network connectivity.")

    requested_name = _normalize_workflow_name(workflow_name)

    path_obj = _validate_local_path(file_path, description="workflow")

    file_extension = path_obj.suffix.lower()
    if file_extension == ".py":
        workflow_config = _load_workflow_from_python(path_obj)
    elif file_extension == ".json":
        workflow_config = _load_workflow_from_json(path_obj)
    else:
        raise CLIError(
            f"Unsupported file type '{file_extension}'. Use .py or .json files."
        )

    # Check if this is a LangGraph script that needs ingestion
    is_langgraph_script = workflow_config.get("_type") == "langgraph_script"

    if is_langgraph_script:
        # Override entrypoint if provided
        if entrypoint:
            workflow_config["entrypoint"] = entrypoint
        result = _upload_langgraph_script(
            state,
            workflow_config,
            workflow_id,
            path_obj,
            requested_name,
        )
    else:
        if requested_name:
            workflow_config["name"] = requested_name
        if workflow_id:
            url = f"/api/workflows/{workflow_id}"
            success_message = (
                f"[green]Workflow '{workflow_id}' updated successfully.[/green]"
            )
        else:
            url = "/api/workflows"
            success_message = "[green]Workflow created successfully.[/green]"
        result = state.client.post(url, json_body=workflow_config)
        state.console.print(success_message)

    render_json(state.console, result, title="Workflow")


@workflow_app.command("download")
def download_workflow(
    ctx: typer.Context,
    workflow_id: WorkflowIdArgument,
    output_path: OutputPathOption = None,
    format_type: FormatOption = "json",
) -> None:
    """Download a workflow configuration to a file or stdout.

    Supports downloading as JSON (default) or Python code format.
    """
    state = _state(ctx)
    workflow, from_cache, stale = load_with_cache(
        state,
        f"workflow:{workflow_id}",
        lambda: state.client.get(f"/api/workflows/{workflow_id}"),
    )
    if from_cache:
        _cache_notice(state, f"workflow {workflow_id}", stale)

    # Get the latest version
    versions, _, _ = load_with_cache(
        state,
        f"workflow:{workflow_id}:versions",
        lambda: state.client.get(f"/api/workflows/{workflow_id}/versions"),
    )
    if not versions:
        raise CLIError(f"Workflow '{workflow_id}' has no versions.")

    latest_version = max(versions, key=lambda entry: entry.get("version", 0))
    graph = latest_version.get("graph", {})

    # Format the output
    if format_type.lower() == "json":
        output_content = _format_workflow_as_json(workflow, graph)
    elif format_type.lower() == "python":
        output_content = _format_workflow_as_python(workflow, graph)
    else:
        raise CLIError(f"Unsupported format '{format_type}'. Use 'json' or 'python'.")

    # Write to file or stdout
    if output_path:
        output_file = _validate_local_path(
            output_path,
            description="output",
            must_exist=False,
            require_file=True,
        )
        output_file.write_text(output_content, encoding="utf-8")
        state.console.print(f"[green]Workflow downloaded to '{output_path}'.[/green]")
    else:
        state.console.print(output_content)


def _load_inputs_from_string(value: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:  # pragma: no cover - handled via CLIError
        raise CLIError(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, Mapping):
        msg = "Inputs payload must be a JSON object."
        raise CLIError(msg)
    return payload


def _validate_local_path(
    path: str | Path,
    *,
    description: str,
    must_exist: bool = True,
    require_file: bool = True,
) -> Path:
    """Resolve a user-supplied path and guard against traversal attempts."""
    path_obj = Path(path).expanduser()
    try:
        resolved = path_obj.resolve(strict=False)
    except RuntimeError as exc:  # pragma: no cover - defensive guard
        raise CLIError(f"Failed to resolve {description} path '{path}': {exc}") from exc

    if not path_obj.is_absolute():
        cwd = Path.cwd().resolve()
        try:
            resolved.relative_to(cwd)
        except ValueError as exc:
            message = (
                f"{description.capitalize()} path '{path}' "
                "escapes the current working directory."
            )
            raise CLIError(message) from exc

    if must_exist and not resolved.exists():
        raise CLIError(f"{description.capitalize()} file '{path}' does not exist.")
    if must_exist and require_file and resolved.exists() and not resolved.is_file():
        raise CLIError(f"{description.capitalize()} path '{path}' is not a file.")
    if not must_exist:
        parent = resolved.parent
        if not parent.exists():
            raise CLIError(
                f"Directory '{parent}' for {description} path '{path}' does not exist."
            )
        if not parent.is_dir():
            raise CLIError(f"Parent of {description} path '{path}' is not a directory.")
        if require_file and resolved.exists() and not resolved.is_file():
            raise CLIError(f"{description.capitalize()} path '{path}' is not a file.")

    return resolved


def _load_inputs_from_path(path: str) -> Mapping[str, Any]:
    path_obj = _validate_local_path(path, description="inputs")
    data = json.loads(path_obj.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise CLIError("Inputs payload must be a JSON object.")
    return data


def _cache_notice(state: CLIState, subject: str, stale: bool) -> None:
    note = "[yellow]Using cached data[/yellow]"
    if stale:
        note += " (older than TTL)"
    state.console.print(f"{note} for {subject}.")


def _strip_main_block(script: str) -> str:
    """Remove if __name__ == "__main__" blocks from Python scripts.

    RestrictedPython doesn't allow variables starting with underscore,
    so we strip out these blocks before ingestion.
    """
    lines = script.split("\n")
    filtered_lines = []
    for line in lines:
        if line.strip().startswith('if __name__ == "__main__"'):
            break
        if line.strip().startswith("if __name__ == '__main__'"):
            break
        filtered_lines.append(line)
    return "\n".join(filtered_lines)


def _load_workflow_from_python(path: Path) -> dict[str, Any]:
    """Load a workflow from a Python file.

    Supports two formats:
    1. SDK Workflow: File defines a 'workflow' variable with a Workflow instance
    2. LangGraph script: File contains raw LangGraph code (returns special format)
    """
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("workflow_module", path)
    if spec is None or spec.loader is None:
        raise CLIError(f"Failed to load Python module from '{path}'.")

    module = importlib.util.module_from_spec(spec)
    sys.modules["workflow_module"] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover
        raise CLIError(f"Failed to execute Python file: {exc}") from exc
    finally:
        sys.modules.pop("workflow_module", None)

    # Check if this is an SDK Workflow file
    if hasattr(module, "workflow"):
        workflow = module.workflow
        if not hasattr(workflow, "to_deployment_payload"):
            msg = "'workflow' variable must be an orcheo_sdk.Workflow instance."
            raise CLIError(msg)

        try:
            return workflow.to_deployment_payload()
        except Exception as exc:  # pragma: no cover
            raise CLIError(f"Failed to generate deployment payload: {exc}") from exc

    # If no 'workflow' variable, treat as raw LangGraph script
    # Return a special marker indicating this needs ingestion API
    try:
        script_content = path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover
        raise CLIError(f"Failed to read file: {exc}") from exc

    # Strip out if __name__ == "__main__" blocks which contain underscore vars
    # that RestrictedPython doesn't allow
    script_content = _strip_main_block(script_content)

    return {
        "_type": "langgraph_script",
        "script": script_content,
        "entrypoint": None,  # Auto-detect entrypoint
    }


def _load_workflow_from_json(path: Path) -> dict[str, Any]:
    """Load a workflow configuration from a JSON file."""
    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
    except json.JSONDecodeError as exc:  # pragma: no cover
        raise CLIError(f"Invalid JSON file: {exc}") from exc
    except Exception as exc:  # pragma: no cover
        raise CLIError(f"Failed to read file: {exc}") from exc

    if not isinstance(data, Mapping):
        raise CLIError("Workflow file must contain a JSON object.")

    if "name" not in data:
        raise CLIError("Workflow configuration must include a 'name' field.")
    if "graph" not in data:
        raise CLIError("Workflow configuration must include a 'graph' field.")

    return dict(data)


def _format_workflow_as_json(
    workflow: Mapping[str, Any], graph: Mapping[str, Any]
) -> str:
    """Format workflow configuration as JSON."""
    output: dict[str, Any] = {
        "name": workflow.get("name"),
        "graph": graph,
    }
    if "metadata" in workflow:
        output["metadata"] = workflow["metadata"]

    return json.dumps(output, indent=2, ensure_ascii=False)


def _format_workflow_as_python(
    workflow: Mapping[str, Any], graph: Mapping[str, Any]
) -> str:
    """Format workflow configuration as Python code.

    Generates a basic Python template that users can customize.
    """
    name = workflow.get("name", "workflow")
    nodes = graph.get("nodes", [])

    lines = [
        '"""Generated workflow configuration."""',
        "",
        "from orcheo_sdk import Workflow, WorkflowNode",
        "from pydantic import BaseModel",
        "",
        "",
    ]

    # Generate node classes (simplified template)
    seen_types: set[str] = set()
    for node in nodes:
        node_type = node.get("type", "Unknown")
        if node_type in seen_types:
            continue
        seen_types.add(node_type)

        lines.extend(
            [
                f"class {node_type}Config(BaseModel):",
                "    # TODO: Define configuration fields",
                "    pass",
                "",
                "",
                f"class {node_type}Node(WorkflowNode[{node_type}Config]):",
                f'    type_name = "{node_type}"',
                "",
                "",
            ]
        )

    # Generate workflow
    lines.extend(
        [
            f'workflow = Workflow(name="{name}")',
            "",
        ]
    )

    # Add nodes
    for node in nodes:
        node_name = node.get("name", "unknown")
        node_type = node.get("type", "Unknown")
        lines.append(
            f"# workflow.add_node({node_type}Node('{node_name}', {node_type}Config()))"
        )

    lines.append("")
    lines.append("# TODO: Configure node dependencies using depends_on parameter")
    lines.append("")

    return "\n".join(lines)
