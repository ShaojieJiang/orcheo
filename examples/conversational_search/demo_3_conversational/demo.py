"""Conversational Search demo - placeholder for future implementation."""

from typing import Any
from langgraph.graph import StateGraph
from orcheo.graph.state import State


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


def graph():
    """Entrypoint for the Orcheo server to load the graph.

    This is a placeholder implementation. The full conversational search workflow
    will include query classification, coreference resolution, query rewriting,
    and topic shift detection.
    """
    workflow = StateGraph(State)

    # Placeholder node
    def placeholder_node(_state: dict) -> dict:
        return {"outputs": {"message": "Demo 3: Conversational Search - Coming Soon"}}

    workflow.add_node("placeholder", placeholder_node)
    workflow.set_entry_point("placeholder")
    workflow.add_edge("placeholder", "__end__")

    return workflow.compile()
