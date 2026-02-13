r"""QReCC query rewriting evaluation workflow.

Loads QReCC conversations, iterates turns through a batch evaluator
(with QueryRewriteNode as the pipeline), computes ROUGE-1 Recall and
Semantic Similarity in parallel, and produces a combined metric report
via AnalyticsExportNode.

Usage:
    orcheo workflow upload examples/evaluation/qrecc_eval.py \\
        --config-file examples/evaluation/config_qrecc.json
    orcheo workflow run <workflow-id>
"""

from typing import Any
from langgraph.graph import END, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.query_processing import QueryRewriteNode
from orcheo.nodes.evaluation.analytics import AnalyticsExportNode
from orcheo.nodes.evaluation.batch import ConversationalBatchEvalNode
from orcheo.nodes.evaluation.datasets import QReCCDatasetNode
from orcheo.nodes.evaluation.metrics import (
    RougeMetricsNode,
    SemanticSimilarityMetricsNode,
)


def build_rewrite_pipeline_graph() -> StateGraph:
    """Build the per-turn rewrite sub-graph for batch evaluation."""
    graph = StateGraph(State)
    graph.add_node(
        "rewrite",
        QueryRewriteNode(
            name="rewrite",
            ai_model="{{config.configurable.rewrite.model}}",
            model_kwargs={"api_key": "[[openai_api_key]]"},
        ),
    )
    graph.set_entry_point("rewrite")
    graph.add_edge("rewrite", END)
    return graph


def build_nodes() -> dict[str, Any]:
    """Create all nodes for the QReCC evaluation workflow."""
    nodes: dict[str, Any] = {}

    nodes["dataset"] = QReCCDatasetNode(
        name="dataset",
        data_path="{{config.configurable.qrecc.data_path}}",
        max_conversations="{{config.configurable.qrecc.max_conversations}}",
    )

    nodes["batch_eval"] = ConversationalBatchEvalNode(
        name="batch_eval",
        conversations_key="conversations",
        prediction_field="query",
        gold_field="gold_rewrite",
        max_conversations="{{config.configurable.qrecc.max_conversations}}",
        max_concurrency="{{config.configurable.qrecc.max_concurrency}}",
        history_window_size="{{config.configurable.qrecc.history_window_size}}",
        include_per_conversation_details=False,
        pipeline=build_rewrite_pipeline_graph(),
    )

    nodes["rouge"] = RougeMetricsNode(
        name="rouge",
        variant="rouge1",
        measure="recall",
    )

    nodes["similarity"] = SemanticSimilarityMetricsNode(
        name="similarity",
        embed_model="{{config.configurable.similarity.embed_model}}",
        model_kwargs={
            "api_key": "[[openai_api_key]]",
            "dimensions": "{{config.configurable.similarity.dimensions}}",
        },
    )

    nodes["analytics_export"] = AnalyticsExportNode(
        name="analytics_export",
        dataset_name="qrecc",
        metric_node_names=["rouge", "similarity"],
        batch_eval_node_name="batch_eval",
    )

    return nodes


async def orcheo_workflow() -> StateGraph:
    """Build the QReCC evaluation workflow graph."""
    nodes = build_nodes()

    workflow = StateGraph(State)
    for node in nodes.values():
        workflow.add_node(node.name, node)

    workflow.set_entry_point("dataset")

    # dataset → batch_eval (sequential)
    workflow.add_edge("dataset", "batch_eval")

    # Fan-out: batch_eval → [rouge, similarity] (parallel)
    workflow.add_edge("batch_eval", "rouge")
    workflow.add_edge("batch_eval", "similarity")

    # Fan-in: [rouge, similarity] → analytics_export
    workflow.add_edge("rouge", "analytics_export")
    workflow.add_edge("similarity", "analytics_export")

    workflow.add_edge("analytics_export", END)

    return workflow
