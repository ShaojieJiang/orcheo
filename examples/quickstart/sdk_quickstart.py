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
                "code": "return {'message': f\"Welcome {state['name']} to Orcheo!\"}",
            },
            {"name": "END", "type": "END"},
        ],
        "edges": [["START", "greet_user"], ["greet_user", "END"]],
    }


async def run() -> None:
    """Execute the quickstart graph locally."""

    graph = build_graph(build_quickstart_graph())
    app = graph.compile()
    result = await app.ainvoke({"name": "Ada", "messages": []})
    print(result["outputs"]["message"])  # noqa: T201 - demo output


if __name__ == "__main__":
    asyncio.run(run())
