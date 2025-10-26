"""Simple LangGraph example demonstrating IfElseNode as a conditional edge.

This example shows how to use IfElseNode to create branching logic in a workflow.
The graph will check if a number is greater than 10 and route to different nodes.
"""

from __future__ import annotations
import asyncio
from typing import Any
from langgraph.graph import END, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.logic import Condition, IfElseNode, SetVariableNode


async def run_example(value: int = 15) -> dict[str, Any]:
    """Run the example workflow with a given value.

    Args:
        value: The value to check against the condition

    Returns:
        The final state of the workflow
    """
    # Initialize nodes
    start = SetVariableNode(
        name="start",
        variables={"value": value, "message": f"Starting with value: {value}"},
    )

    # Create IfElseNode that checks if value > 10
    # Note: We use the value directly here for simplicity in this example
    # In a real Orcheo workflow with JSON config, variable interpolation would
    # be handled
    check_value = IfElseNode(
        name="check_value",
        conditions=[
            Condition(
                left=value,  # Pass the value directly
                operator="greater_than",
                right=10,
            )
        ],
        condition_logic="and",
    )

    high_value = SetVariableNode(
        name="high_value",
        variables={
            "value": "{{results.start.value}}",
            "result": "High value path: value is > 10",
            "path_taken": "high",
        },
    )
    low_value = SetVariableNode(
        name="low_value",
        variables={
            "value": "{{results.start.value}}",
            "result": "Low value path: value is <= 10",
            "path_taken": "low",
        },
    )

    # Build the graph
    graph = StateGraph(State)

    # Add nodes to the graph
    graph.add_node("start", start)
    graph.add_node("high_value", high_value)
    graph.add_node("low_value", low_value)

    # Define edges
    # Add conditional edge using check_value directly as the routing function
    # The IfElseNode (as a DecisionNode) returns "true" or "false" directly
    # Note: We don't add check_value as a node, but use it directly as a
    # conditional edge
    graph.add_conditional_edges(
        "start",
        check_value,
        {
            "true": "high_value",
            "false": "low_value",
        },
    )

    # Both paths end the workflow
    graph.add_edge("high_value", END)
    graph.add_edge("low_value", END)

    # Set entry point
    graph.set_entry_point("start")

    # Compile and run
    workflow = graph.compile()

    # Initialize state
    initial_state: State = {"inputs": {}, "messages": [], "results": {}}

    # Execute the workflow
    final_state = await workflow.ainvoke(initial_state)

    return final_state


async def main() -> None:
    """Run examples with different values."""
    print("=" * 60)
    print("LangGraph IfElseNode Conditional Edge Example")
    print("=" * 60)

    # Example 1: High value (> 10)
    print("\n--- Example 1: Value = 15 (should take high path) ---")
    result1 = await run_example(value=15)
    final_result = result1["results"].get("high_value") or result1["results"].get(
        "low_value"
    )

    print(f"Value: {final_result['value']}")
    print(f"Result: {final_result['result']}")
    print(f"Path taken: {final_result['path_taken']}")

    # Example 2: Low value (<= 10)
    print("\n--- Example 2: Value = 5 (should take low path) ---")
    result2 = await run_example(value=5)
    final_result = result2["results"].get("high_value") or result2["results"].get(
        "low_value"
    )

    print(f"Value: {final_result['value']}")
    print(f"Result: {final_result['result']}")
    print(f"Path taken: {final_result['path_taken']}")

    # Example 3: Edge case (exactly 10)
    print("\n--- Example 3: Value = 10 (should take low path) ---")
    result3 = await run_example(value=10)
    final_result = result3["results"].get("high_value") or result3["results"].get(
        "low_value"
    )

    print(f"Value: {final_result['value']}")
    print(f"Result: {final_result['result']}")
    print(f"Path taken: {final_result['path_taken']}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
