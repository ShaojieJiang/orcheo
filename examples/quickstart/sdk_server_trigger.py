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
from typing import Any
import websockets
from orcheo_sdk import (
    OrcheoClient,
    Workflow,
    WorkflowNode,
    WorkflowRunContext,
    WorkflowState,
)
from pydantic import BaseModel


class PythonCodeConfig(BaseModel):
    """Configuration schema for the PythonCode node."""

    code: str


class PythonCodeNode(WorkflowNode[PythonCodeConfig, dict[str, Any]]):
    """Convenience wrapper that exports PythonCode nodes from the SDK."""

    type_name = "PythonCode"

    async def run(  # pragma: no cover - executed remotely by the Orcheo backend
        self,
        state: WorkflowState,
        context: WorkflowRunContext,
    ) -> dict[str, Any]:
        """SDK nodes only export configuration; execution happens on the server."""
        msg = "PythonCodeNode.run should not execute locally in this example"
        raise RuntimeError(msg)


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
                    "greeting = state['outputs']['greet_user']['message']\n"
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
    websocket_url = client.websocket_url("sdk-demo")
    payload = client.build_payload(
        graph_config,
        inputs={"name": "Ada Lovelace"},
    )

    async with websockets.connect(websocket_url) as websocket:
        await websocket.send(json.dumps(payload))

        async for message in websocket:
            update = json.loads(message)
            print(f"Update: {update}")
            if update.get("status") in {"completed", "error"}:
                break


if __name__ == "__main__":
    asyncio.run(run())
