"""Evaluation & Research demo - placeholder for future implementation."""

from typing import Any
from langgraph.graph import StateGraph
from orcheo.graph.state import State


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


def graph():
    """Entrypoint for the Orcheo server to load the graph.

    This is a placeholder implementation. The full evaluation workflow will
    include A/B testing, retrieval evaluation, answer quality assessment,
    and feedback collection.
    """
    workflow = StateGraph(State)

    # Placeholder node
    def placeholder_node(_state: dict) -> dict:
        return {"outputs": {"message": "Demo 5: Evaluation & Research - Coming Soon"}}

    workflow.add_node("placeholder", placeholder_node)
    workflow.set_entry_point("placeholder")
    workflow.add_edge("placeholder", "__end__")

    return workflow.compile()
