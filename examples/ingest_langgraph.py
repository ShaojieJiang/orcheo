"""Submit a LangGraph Python script to the Orcheo backend.

Prerequisites:
    1. Install dependencies: `uv sync --all-groups`
    2. Run the backend locally: `make dev-server`

With the server running, execute this script via
`uv run python examples/ingest_langgraph.py` to register the LangGraph
workflow and inspect the stored version summary.
"""

from __future__ import annotations

import textwrap
from typing import Any

import httpx


LANGGRAPH_SCRIPT = textwrap.dedent(
    """
    from langgraph.graph import StateGraph
    from orcheo.graph.state import State

    def _greet_user(state: State) -> dict[str, str]:
        name = state["inputs"].get("name", "there")
        return {"greeting": f"Hello {name}!"}

    def _format_message(state: State) -> dict[str, str]:
        greeting = state["results"]["greet_user"]["greeting"]
        return {"shout": greeting.upper()}

    def build_graph() -> StateGraph[State]:
        graph = StateGraph(State)
        graph.add_node("greet_user", _greet_user)
        graph.add_node("format_message", _format_message)
        graph.add_edge("greet_user", "format_message")
        graph.set_entry_point("greet_user")
        graph.set_finish_point("format_message")
        return graph
    """
)


def _create_workflow(client: httpx.Client) -> str:
    """Create a workflow that will receive the ingested LangGraph version."""
    response = client.post(
        "/workflows",
        json={
            "name": "langgraph-import-demo",
            "slug": "langgraph-import-demo",
            "description": "Workflow imported from a LangGraph Python script",
            "tags": ["example", "langgraph"],
            "actor": "example-script",
        },
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    workflow_id = payload["id"]
    print(f"Created workflow {workflow_id} ({payload['name']})")
    return workflow_id


def _ingest_langgraph_version(client: httpx.Client, workflow_id: str) -> dict[str, Any]:
    """Submit the LangGraph script to create a new workflow version."""
    response = client.post(
        f"/workflows/{workflow_id}/versions/ingest",
        json={
            "script": LANGGRAPH_SCRIPT,
            "entrypoint": "build_graph",
            "metadata": {"language": "python", "source": "langgraph"},
            "notes": "Initial LangGraph import",
            "created_by": "example-script",
        },
    )
    response.raise_for_status()
    version: dict[str, Any] = response.json()
    print(
        "Registered workflow version "
        f"{version['version_number']} for workflow {workflow_id}"
    )
    return version


def main() -> None:
    """Drive the example ingestion flow."""
    with httpx.Client(base_url="http://localhost:8000/api", timeout=10.0) as client:
        workflow_id = _create_workflow(client)
        version = _ingest_langgraph_version(client, workflow_id)

    summary = version["graph"].get("summary", {})
    print("\nGraph summary:")
    print(f"  nodes: {summary.get('nodes')}")
    print(f"  edges: {summary.get('edges')}")
    print(f"  entrypoint: {summary.get('entrypoint')}")
    print(f"  finish_points: {summary.get('finish_points')}")


if __name__ == "__main__":
    main()
