"""Quickstart example for the SDK-driven workflow path."""

from __future__ import annotations
import asyncio
from typing import Any
from orcheo.graph.builder import build_graph


def build_quickstart_graph() -> dict[str, Any]:
    """Return the graph configuration shared with the canvas example."""
    return {
        "nodes": [
            {"name": "START", "type": "START"},
            {
                "name": "greet_user",
                "type": "PythonCode",
                "code": (
                    "return {'message': "
                    "f\"Welcome {state['inputs']['name']} to Orcheo!\"}"
                ),
            },
            {"name": "END", "type": "END"},
        ],
        "edges": [["START", "greet_user"], ["greet_user", "END"]],
    }


async def run() -> None:
    """Execute the quickstart graph locally."""
    graph = build_graph(build_quickstart_graph())
    app = graph.compile()
    result = await app.ainvoke(
        {
            "inputs": {"name": "Ada"},
            "messages": [],
            "results": {},
        }
    )
    print(result["results"]["greet_user"]["message"])  # noqa: T201 - demo output


if __name__ == "__main__":
    asyncio.run(run())
