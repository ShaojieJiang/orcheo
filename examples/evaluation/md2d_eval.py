r"""MultiDoc2Dial grounded generation evaluation workflow.

Loads MultiDoc2Dial conversations, iterates turns through a batch evaluator
(with a full retrieval-generation pipeline), computes Token F1, SacreBLEU,
and ROUGE-L in parallel, and produces a combined metric report via
AnalyticsExportNode.

Usage:
    orcheo workflow upload examples/evaluation/md2d_eval.py \\
        --config-file examples/evaluation/config_md2d.json
    orcheo workflow run <workflow-id>
"""

from typing import Any
from langgraph.graph import END, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.generation import GroundedGeneratorNode
from orcheo.nodes.conversational_search.query_processing import (
    ContextCompressorNode,
    QueryRewriteNode,
)
from orcheo.nodes.conversational_search.retrieval import DenseSearchNode
from orcheo.nodes.conversational_search.vector_store import PineconeVectorStore
from orcheo.nodes.evaluation.analytics import AnalyticsExportNode
from orcheo.nodes.evaluation.batch import ConversationalBatchEvalNode
from orcheo.nodes.evaluation.datasets import MultiDoc2DialDatasetNode
from orcheo.nodes.evaluation.metrics import (
    BleuMetricsNode,
    RougeMetricsNode,
    TokenF1MetricsNode,
)


def build_generation_pipeline_graph() -> StateGraph:
    """Build the per-turn retrieval-generation sub-graph for batch evaluation."""
    vector_store = PineconeVectorStore(
        index_name="{{config.configurable.vector_store.pinecone.index_name}}",
        namespace="{{config.configurable.vector_store.pinecone.namespace}}",
        client_kwargs={"api_key": "[[pinecone_api_key]]"},
    )
    graph = StateGraph(State)
    graph.add_node(
        "rewrite",
        QueryRewriteNode(
            name="rewrite",
            ai_model="{{config.configurable.generation.model}}",
            model_kwargs={"api_key": "[[openai_api_key]]"},
        ),
    )
    graph.add_node(
        "search",
        DenseSearchNode(
            name="search",
            vector_store=vector_store,
            embed_model="{{config.configurable.retrieval.embed_model}}",
            model_kwargs={"api_key": "[[openai_api_key]]"},
            top_k="{{config.configurable.retrieval.top_k}}",
        ),
    )
    graph.add_node(
        "compress",
        ContextCompressorNode(
            name="compress",
            results_field="search",
        ),
    )
    graph.add_node(
        "generate",
        GroundedGeneratorNode(
            name="generate",
            ai_model="{{config.configurable.generation.model}}",
            context_result_key="compress",
            model_kwargs={"api_key": "[[openai_api_key]]"},
        ),
    )
    graph.set_entry_point("rewrite")
    graph.add_edge("rewrite", "search")
    graph.add_edge("search", "compress")
    graph.add_edge("compress", "generate")
    graph.add_edge("generate", END)
    return graph


def build_nodes() -> dict[str, Any]:
    """Create all nodes for the MultiDoc2Dial evaluation workflow."""
    nodes: dict[str, Any] = {}

    nodes["dataset"] = MultiDoc2DialDatasetNode(
        name="dataset",
        data_path="{{config.configurable.md2d.data_path}}",
        max_conversations="{{config.configurable.md2d.max_conversations}}",
    )

    nodes["batch_eval"] = ConversationalBatchEvalNode(
        name="batch_eval",
        conversations_key="conversations",
        prediction_field="reply",
        gold_field="gold_response",
        max_conversations="{{config.configurable.md2d.max_conversations}}",
        pipeline=build_generation_pipeline_graph(),
    )

    nodes["token_f1"] = TokenF1MetricsNode(name="token_f1")

    nodes["bleu"] = BleuMetricsNode(name="bleu")

    nodes["rouge"] = RougeMetricsNode(
        name="rouge",
        variant="rougeL",
        measure="fmeasure",
    )

    nodes["analytics_export"] = AnalyticsExportNode(
        name="analytics_export",
        dataset_name="multidoc2dial",
        metric_node_names=["token_f1", "bleu", "rouge"],
        batch_eval_node_name="batch_eval",
    )

    return nodes


async def orcheo_workflow() -> StateGraph:
    """Build the MultiDoc2Dial evaluation workflow graph."""
    nodes = build_nodes()

    workflow = StateGraph(State)
    for node in nodes.values():
        workflow.add_node(node.name, node)

    workflow.set_entry_point("dataset")

    # dataset → batch_eval (sequential)
    workflow.add_edge("dataset", "batch_eval")

    # Fan-out: batch_eval → [token_f1, bleu, rouge] (parallel)
    workflow.add_edge("batch_eval", "token_f1")
    workflow.add_edge("batch_eval", "bleu")
    workflow.add_edge("batch_eval", "rouge")

    # Fan-in: [token_f1, bleu, rouge] → analytics_export
    workflow.add_edge("token_f1", "analytics_export")
    workflow.add_edge("bleu", "analytics_export")
    workflow.add_edge("rouge", "analytics_export")

    workflow.add_edge("analytics_export", END)

    return workflow
