"""Author a workflow with the SDK and execute it via the Orcheo server.

Prerequisites:
    1. Install dependencies: `uv sync --all-groups`
    2. Run the backend locally: `make dev-server`

Once the server is running, execute this script with `uv run python
examples/quickstart/sdk_server_trigger.py` to see the workflow updates
streaming back over the websocket connection.
"""

from __future__ import annotations
import asyncio
import json
import websockets
from orcheo_sdk import (
    OrcheoClient,
    Workflow,
    WorkflowNode,
)
from pydantic import BaseModel
from websockets import exceptions as ws_exceptions


class PythonCodeConfig(BaseModel):
    """Configuration schema for the PythonCode node."""

    code: str


class PythonCodeNode(WorkflowNode[PythonCodeConfig]):
    """Convenience wrapper that exports PythonCode nodes from the SDK."""

    type_name = "PythonCode"


def build_workflow() -> Workflow:
    """Create a multi-step workflow that greets and formats a user name."""
    workflow = Workflow(name="sdk-websocket-demo")

    workflow.add_node(
        PythonCodeNode(
            "greet_user",
            PythonCodeConfig(
                code=(
                    "return {'message': "
                    "f\"Welcome {state['inputs']['name']} to Orcheo!\"}"
                ),
            ),
        )
    )

    workflow.add_node(
        PythonCodeNode(
            "format_message",
            PythonCodeConfig(
                code=(
                    "greeting = state['results']['greet_user']['message']\n"
                    "return {'shout': greeting.upper()}"
                ),
            ),
        ),
        depends_on=["greet_user"],
    )

    return workflow


async def run() -> None:
    """Connect to the server, trigger the workflow, and stream updates."""
    workflow = build_workflow()
    graph_config = workflow.to_graph_config()

    client = OrcheoClient(base_url="http://localhost:8000")
    workflow_identifier = "sdk-websocket-demo"
    websocket_url = client.websocket_url(workflow_identifier)
    payload = client.build_payload(
        graph_config,
        inputs={"name": "Ada Lovelace"},
    )

    try:
        async with websockets.connect(
            websocket_url,
            open_timeout=5,
            close_timeout=5,
        ) as websocket:
            await websocket.send(json.dumps(payload))

            async for message in websocket:
                update = json.loads(message)
                print(f"Update: {update}")
                status = update.get("status")
                if status == "error":
                    error_detail = update.get("error") or "Unknown error"
                    print(f"Workflow execution failed: {error_detail}")
                    break
                if status == "completed":
                    break
    except (ConnectionRefusedError, OSError) as exc:
        print(
            "Failed to connect to the Orcheo server. "
            "Ensure `make dev-server` is running before executing this script."
        )
        print(f"Connection error: {exc}")
    except TimeoutError:
        print(
            "Timed out while establishing or closing the WebSocket connection. "
            "Retry once the server is reachable."
        )
    except ws_exceptions.InvalidStatusCode as exc:
        print(
            "The server rejected the WebSocket handshake. Verify the workflow "
            "identifier and backend availability."
        )
        print(f"HTTP status: {exc.status_code}")
    except ws_exceptions.WebSocketException as exc:
        print(f"WebSocket communication error: {exc}")


if __name__ == "__main__":
    asyncio.run(run())
