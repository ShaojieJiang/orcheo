"""Streaming helpers for workflow execution."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from orcheo_sdk.cli.output import render_json
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.services import get_latest_workflow_version_data


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
    from orcheo_sdk.cli import workflow as workflow_module

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
            process_messages = getattr(
                workflow_module,
                "_process_stream_messages",
                _process_stream_messages,
            )
            return await process_messages(state, websocket)
    except (ConnectionRefusedError, OSError) as exc:
        state.console.print(
            "[red]Failed to connect to server.[/red]\n"
            "[dim]Ensure the backend is running.[/dim]"
        )
        state.console.print(f"[dim]Error: {exc}[/dim]")
        return "connection_error"
    except getattr(workflow_module, "TimeoutError", TimeoutError):
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
    from orcheo_sdk.cli import workflow as workflow_module

    handle_status = getattr(
        workflow_module,
        "_handle_status_update",
        _handle_status_update,
    )
    handle_node_event = getattr(
        workflow_module,
        "_handle_node_event",
        _handle_node_event,
    )

    async for message in websocket:
        update = json.loads(message)
        status = update.get("status")

        if status:
            final_status = handle_status(state, update)
            if final_status:
                return final_status
            continue

        handle_node_event(state, update)

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
    from orcheo_sdk.cli import workflow as workflow_module

    render_output = getattr(
        workflow_module,
        "_render_node_output",
        _render_node_output,
    )

    if not (node and event):
        return

    if event == "on_chain_start":
        state.console.print(f"[blue]→ {node}[/blue] [dim]starting...[/dim]")
    elif event == "on_chain_end":
        state.console.print(f"[green]✓ {node}[/green]")
        if payload_data:
            render_output(state, payload_data)
    elif event == "on_chain_error":
        error_msg = payload_data.get("error") if payload_data else "Unknown"
        state.console.print(f"[red]✗ {node}[/red] [dim]{error_msg}[/dim]")
    else:
        state.console.print(f"[dim][{event}] {node}: {payload_data}[/dim]")


def _render_node_output(state: CLIState, data: Any) -> None:
    """Render node output in a compact, readable format."""
    if not data:
        return

    from orcheo_sdk.cli import workflow as workflow_module

    render_json_fn = getattr(
        workflow_module,
        "render_json",
        render_json,
    )

    if isinstance(data, dict):
        if len(data) <= 3 and all(
            isinstance(v, str | int | float | bool) for v in data.values()
        ):
            items = [f"{k}={v!r}" for k, v in data.items()]
            state.console.print(f"  [dim]{', '.join(items)}[/dim]")
        else:
            render_json_fn(state.console, data, title=None)
    elif isinstance(data, str) and len(data) < 100:
        state.console.print(f"  [dim]{data}[/dim]")
    else:
        import json as json_module

        try:
            formatted = json_module.dumps(data, indent=2, default=str)
            state.console.print(f"[dim]{formatted}[/dim]")
        except Exception:  # pragma: no cover
            state.console.print(f"  [dim]{data!r}[/dim]")


def _prepare_streaming_graph(
    state: CLIState,
    workflow_id: str,
) -> dict[str, Any] | None:
    """Fetch latest workflow graph configuration for streaming."""
    latest_version = get_latest_workflow_version_data(state.client, workflow_id)
    graph_raw = latest_version.get("graph")
    if isinstance(graph_raw, Mapping):
        return dict(graph_raw)
    return None


__all__ = [
    "_stream_workflow_run",
    "_process_stream_messages",
    "_handle_status_update",
    "_handle_node_event",
    "_render_node_output",
    "_prepare_streaming_graph",
]
