"""Simple LangGraph example demonstrating IfElseNode as a conditional edge.

This example shows how to use IfElseNode to create branching logic in a workflow.
The graph will check if a number is greater than 10 and route to different nodes.
"""

from __future__ import annotations
import asyncio
from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.logic import Condition, IfElseNode


class StartNode(TaskNode):
    """Simple node that provides an initial value."""

    value: int = Field(default=15, description="The value to check")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the initial value."""
        return {"value": self.value, "message": f"Starting with value: {self.value}"}


class HighValueNode(TaskNode):
    """Node executed when value is high (> 10)."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Process high value."""
        results = state.get("results", {})
        start_result = results.get("start", {})
        value = start_result.get("value", 0)
        return {
            "result": f"High value path: {value} is > 10",
            "path_taken": "high",
        }


class LowValueNode(TaskNode):
    """Node executed when value is low (<= 10)."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Process low value."""
        results = state.get("results", {})
        start_result = results.get("start", {})
        value = start_result.get("value", 0)
        return {
            "result": f"Low value path: {value} is <= 10",
            "path_taken": "low",
        }


async def run_example(value: int = 15) -> dict[str, Any]:
    """Run the example workflow with a given value.

    Args:
        value: The value to check against the condition

    Returns:
        The final state of the workflow
    """
    # Initialize nodes
    start = StartNode(name="start", value=value)

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

    high_value = HighValueNode(name="high_value")
    low_value = LowValueNode(name="low_value")

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
    initial_state: State = {"results": {}}

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
