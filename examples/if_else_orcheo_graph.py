"""Orcheo graph example demonstrating conditional branching.

This example shows how to create branching logic in a workflow using Orcheo's
build_graph function. The graph will check if a number is greater than 10 and
route to different nodes using conditional edges.

Note: While Orcheo has an IfElseNode class, it's designed to work as a
DecisionNode in LangGraph-style code (see if_else_langgraph.py). In the
build_graph/JSON config approach, conditional branching is achieved by:
1. Creating a node that returns a routing key (e.g., "true" or "false")
2. Using conditional_edges to route based on that key
"""

from __future__ import annotations
import asyncio
from typing import Any
from orcheo.graph.builder import build_graph


def build_if_else_graph(value: int = 15) -> dict[str, Any]:
    """Build the if-else graph configuration.

    Args:
        value: The value to check against the condition

    Returns:
        Graph configuration dictionary
    """
    return {
        "nodes": [
            {"name": "START", "type": "START"},
            {
                "name": "start",
                "type": "PythonCode",
                "code": (
                    f"return {{'value': {value}, "
                    f"'message': f'Starting with value: {value}'}}"
                ),
            },
            {
                "name": "high_value",
                "type": "PythonCode",
                "code": (
                    "value = state['results']['start']['value']\n"
                    "return {\n"
                    "    'result': f'High value path: {value} is > 10',\n"
                    "    'path_taken': 'high',\n"
                    "}"
                ),
            },
            {
                "name": "low_value",
                "type": "PythonCode",
                "code": (
                    "value = state['results']['start']['value']\n"
                    "return {\n"
                    "    'result': f'Low value path: {value} is <= 10',\n"
                    "    'path_taken': 'low',\n"
                    "}"
                ),
            },
            {"name": "END", "type": "END"},
        ],
        "edge_nodes": [
            {
                "name": "check_value",
                "type": "IfElseNode",
                "conditions": [
                    {
                        "left": "{{results.start.value}}",
                        "operator": "greater_than",
                        "right": 10,
                    }
                ],
                "condition_logic": "and",
            },
        ],
        "edges": [
            ["START", "start"],
            ["high_value", "END"],
            ["low_value", "END"],
        ],
        "conditional_edges": [
            {
                "source": "start",
                "path": "check_value",
                "mapping": {
                    "true": "high_value",
                    "false": "low_value",
                },
            }
        ],
    }


async def run_example(value: int = 15) -> dict[str, Any]:
    """Run the example workflow with a given value.

    Args:
        value: The value to check against the condition

    Returns:
        The final state of the workflow
    """
    graph = build_graph(build_if_else_graph(value))
    app = graph.compile()

    # Initialize state
    initial_state: dict[str, Any] = {
        "inputs": {},
        "messages": [],
        "results": {},
    }

    # Execute the workflow
    final_state = await app.ainvoke(initial_state)

    return final_state


async def main() -> None:
    """Run examples with different values."""
    print("=" * 60)
    print("Orcheo Conditional Branching Example")
    print("=" * 60)

    # Example 1: High value (> 10)
    print("\n--- Example 1: Value = 15 (should take high path) ---")
    result1 = await run_example(value=15)
    final_result = result1["results"].get("high_value") or result1["results"].get(
        "low_value"
    )

    print(f"Final result: {final_result['result']}")
    print(f"Path taken: {final_result['path_taken']}")

    # Example 2: Low value (<= 10)
    print("\n--- Example 2: Value = 5 (should take low path) ---")
    result2 = await run_example(value=5)
    final_result = result2["results"].get("high_value") or result2["results"].get(
        "low_value"
    )

    print(f"Final result: {final_result['result']}")
    print(f"Path taken: {final_result['path_taken']}")

    # Example 3: Edge case (exactly 10)
    print("\n--- Example 3: Value = 10 (should take low path) ---")
    result3 = await run_example(value=10)
    final_result = result3["results"].get("high_value") or result3["results"].get(
        "low_value"
    )

    print(f"Final result: {final_result['result']}")
    print(f"Path taken: {final_result['path_taken']}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
