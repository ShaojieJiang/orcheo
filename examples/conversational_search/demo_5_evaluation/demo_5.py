"""Evaluation & Research demo - placeholder for future implementation."""

from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode


# Default configuration inlined for server execution
DEFAULT_CONFIG: dict[str, Any] = {
    "dataset": {
        "golden_queries_path": "../data/golden/golden_dataset.json",
        "relevance_labels_path": "../data/labels/relevance_labels.json",
    },
    "variants": [
        {"name": "vector_only", "traffic_percentage": 50},
        {"name": "hybrid_fusion", "traffic_percentage": 50},
    ],
    "evaluation": {
        "retrieval_metrics": ["recall@5", "recall@10", "mrr", "ndcg@10"],
        "answer_quality_metrics": ["faithfulness", "relevance", "completeness"],
    },
}


class PlaceholderMessageNode(TaskNode):
    """Simple placeholder TaskNode until the evaluation workflow is ready."""

    message: str = Field(description="Placeholder message shown to the user")

    async def run(self, _state: State, _config: RunnableConfig) -> dict[str, Any]:
        """Return the placeholder response while the workflow is under development."""
        return {"outputs": {"message": self.message}}


async def build_graph() -> StateGraph:
    """Entrypoint for the Orcheo server to load the graph.

    This is a placeholder implementation. The full evaluation workflow will
    include A/B testing, retrieval evaluation, answer quality assessment,
    and feedback collection.
    """
    workflow = StateGraph(State)

    placeholder = PlaceholderMessageNode(
        name="placeholder",
        message="Demo 5: Evaluation & Research - Coming Soon",
    )

    workflow.add_node("placeholder", placeholder)
    workflow.set_entry_point("placeholder")
    workflow.add_edge("placeholder", END)

    return workflow
