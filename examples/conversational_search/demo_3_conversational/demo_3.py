"""Conversational Search demo - placeholder for future implementation."""

from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode


# Default configuration inlined for server execution
DEFAULT_CONFIG: dict[str, Any] = {
    "conversation": {
        "max_turns": 20,
        "memory_store": "in_memory",
    },
    "query_processing": {
        "classifier": {"model": "gpt-4o-mini"},
        "coreference_resolver": {"method": "transformer"},
        "query_rewrite": {"strategy": "conversational_expansion"},
    },
}


class PlaceholderMessageNode(TaskNode):
    """Simple placeholder TaskNode until the full conversational workflow is ready."""

    message: str = Field(description="Placeholder message shown to the user")

    async def run(self, _state: State, _config: RunnableConfig) -> dict[str, Any]:
        """Return the placeholder response while the workflow is under development."""
        return {"outputs": {"message": self.message}}


async def build_graph() -> StateGraph:
    """Entrypoint for the Orcheo server to load the graph.

    This is a placeholder implementation. The full conversational search workflow
    will include query classification, coreference resolution, query rewriting,
    and topic shift detection.
    """
    workflow = StateGraph(State)

    placeholder = PlaceholderMessageNode(
        name="placeholder",
        message="Demo 3: Conversational Search - Coming Soon",
    )

    workflow.add_node("placeholder", placeholder)
    workflow.set_entry_point("placeholder")
    workflow.add_edge("placeholder", END)

    return workflow
