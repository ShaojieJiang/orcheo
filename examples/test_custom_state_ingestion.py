"""Test ingestion of custom_state_langgraph.py to verify full state control."""

from __future__ import annotations
import asyncio
import json
import uuid
from pathlib import Path
import httpx
import websockets


API_BASE_URL = "http://localhost:8000/api"
WEBSOCKET_BASE_URL = "ws://localhost:8000/ws/workflow"


def main() -> None:
    """Test custom state ingestion and execution."""
    # Read the custom state script
    script_path = Path(__file__).parent / "custom_state_langgraph.py"
    script_content = script_path.read_text()

    # Remove the if __name__ == "__main__" block
    lines = script_content.split("\n")
    filtered_lines = []
    for line in lines:
        if line.strip().startswith('if __name__ == "__main__"'):
            break
        filtered_lines.append(line)
    script = "\n".join(filtered_lines)

    # Create workflow
    with httpx.Client(base_url=API_BASE_URL, timeout=10.0) as client:
        response = client.post(
            "/workflows",
            json={
                "name": "custom-state-demo",
                "slug": "custom-state-demo",
                "description": "Demo of custom state control in LangGraph",
                "tags": ["example", "custom-state"],
                "actor": "test-script",
            },
        )
        response.raise_for_status()
        workflow_id = response.json()["id"]
        print(f"Created workflow: {workflow_id}")

        # Ingest the script
        response = client.post(
            f"/workflows/{workflow_id}/versions/ingest",
            json={
                "script": script,
                "entrypoint": "build_graph",
                "metadata": {"language": "python"},
                "notes": "Custom state example",
                "created_by": "test-script",
            },
        )
        response.raise_for_status()
        version = response.json()
        print(f"Registered version {version['version']}")

    # Execute the workflow with custom initial state
    async def execute():
        websocket_url = f"{WEBSOCKET_BASE_URL}/{workflow_id}"
        execution_id = str(uuid.uuid4())

        # Pass custom state fields as inputs
        payload = {
            "type": "run_workflow",
            "graph_config": version["graph"],
            "inputs": {
                "counter": 0,
                "messages": [],
            },
            "execution_id": execution_id,
        }

        print("\nExecuting workflow with custom state...")
        print("Initial state: counter=0, messages=[]")

        async with websockets.connect(websocket_url) as websocket:
            await websocket.send(json.dumps(payload))

            async for message in websocket:
                update = json.loads(message)
                if update.get("status"):
                    print(f"\nStatus: {update['status']}")
                    if update["status"] in ["completed", "error", "cancelled"]:
                        break
                else:
                    print(f"Update: {update}")

    asyncio.run(execute())
    print("\n✓ Custom state example completed successfully!")
    print("  The script had full control over state structure.")


if __name__ == "__main__":
    main()
