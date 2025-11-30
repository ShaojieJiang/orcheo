"""Hybrid Search demo - placeholder for future implementation."""

from typing import Any
from langgraph.graph import StateGraph
from orcheo.graph.state import State


# Default configuration inlined for server execution
DEFAULT_CONFIG: dict[str, Any] = {
    "retrieval": {
        "bm25": {"top_k": 10},
        "vector": {"top_k": 10},
        "web_search": {"max_results": 5},
        "fusion": {
            "strategy": "reciprocal_rank_fusion",
            "weights": {"vector": 0.5, "bm25": 0.3, "web": 0.2},
        },
        "reranker": {"model": "cross-encoder/ms-marco-MiniLM-L-6-v2", "top_k": 5},
    }
}


def graph():
    """Entrypoint for the Orcheo server to load the graph.

    This is a placeholder implementation. The full hybrid search workflow
    will combine BM25, vector search, web search with fusion and re-ranking.
    """
    workflow = StateGraph(State)

    # Placeholder node
    def placeholder_node(_state: dict) -> dict:
        return {"outputs": {"message": "Demo 2: Hybrid Search - Coming Soon"}}

    workflow.add_node("placeholder", placeholder_node)
    workflow.set_entry_point("placeholder")
    workflow.add_edge("placeholder", "__end__")

    return workflow.compile()
