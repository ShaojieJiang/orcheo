"""Hybrid Search demo - placeholder for future implementation."""

from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode


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


class PlaceholderMessageNode(TaskNode):
    """Simple placeholder TaskNode until the full hybrid workflow is ready."""

    message: str = Field(description="Placeholder message shown to the user")

    async def run(self, _state: State, _config: RunnableConfig) -> dict[str, Any]:
        """Return the placeholder response while the workflow is under development."""
        return {"outputs": {"message": self.message}}


async def build_graph() -> StateGraph:
    """Entrypoint for the Orcheo server to load the graph.

    This is a placeholder implementation. The full hybrid search workflow
    will combine BM25, vector search, web search with fusion and re-ranking.
    """
    workflow = StateGraph(State)

    placeholder = PlaceholderMessageNode(
        name="placeholder",
        message="Demo 2: Hybrid Search - Coming Soon",
    )

    workflow.add_node("placeholder", placeholder)
    workflow.set_entry_point("placeholder")
    workflow.add_edge("placeholder", END)

    return workflow
