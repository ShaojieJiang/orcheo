"""Hybrid search demo: retrieve + fuse over prebuilt Pinecone indexes.

Configurable inputs (config.json):
- dense_top_k: Number of dense search results to retrieve
- dense_similarity_threshold: Minimum similarity score for dense results
- dense_embedding_method: Registered dense embedding method identifier
- sparse_top_k: Number of sparse search results to retrieve
- sparse_score_threshold: Minimum score for sparse results
- sparse_vector_store_candidate_k: Candidate pool size for sparse search
- sparse_embedding_method: Registered sparse embedding method identifier
- web_search_provider: Web search provider (default: tavily)
- web_search_max_results: Maximum web search results
- web_search_search_depth: Web search depth (basic or advanced)
- fusion_rrf_k: Reciprocal rank fusion k parameter
- fusion_top_k: Number of results after fusion
- context_max_tokens: Maximum tokens for context summarization
- context_summary_model: Model for summarization
- vector_store_index_dense: Pinecone index name for dense vectors
- vector_store_index_sparse: Pinecone index name for sparse vectors
- vector_store_namespace: Pinecone namespace for both stores
- reranker_model: Reranker model name
- reranker_top_n: Number of results after reranking
- generation_model: Model for grounded generation
"""

from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.generation import (
    CitationsFormatterNode,
    GroundedGeneratorNode,
)
from orcheo.nodes.conversational_search.query_processing import ContextCompressorNode
from orcheo.nodes.conversational_search.retrieval import (
    DenseSearchNode,
    HybridFusionNode,
    PineconeRerankNode,
    SparseSearchNode,
    WebSearchNode,
)
from orcheo.nodes.conversational_search.vector_store import PineconeVectorStore


def default_retriever_map() -> dict[str, str]:
    """Return the default mapping between retriever types and result keys."""
    return {"dense": "dense_search", "sparse": "sparse_search", "web": "web_search"}


class RetrievalCollectorNode(TaskNode):
    """Collect outputs from multiple retrievers for hybrid fusion."""

    retriever_map: dict[str, str] = Field(default_factory=default_retriever_map)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Gather retriever outputs and ensure at least one result is present."""
        del config
        collected: dict[str, Any] = {}
        results = state.get("results", {})
        for logical_name, result_key in self.retriever_map.items():
            payload = results.get(result_key)
            if not payload:
                continue
            collected[logical_name] = payload

        if not collected:
            msg = "RetrievalCollectorNode requires at least one retriever result"
            raise ValueError(msg)
        return collected


async def build_graph() -> StateGraph:
    """Assemble and return the hybrid search workflow graph."""
    dense_store = PineconeVectorStore(
        index_name="{{config.configurable.vector_store_index_dense}}",
        namespace="{{config.configurable.vector_store_namespace}}",
        client_kwargs={"api_key": "[[pinecone_api_key]]"},
    )
    sparse_store = PineconeVectorStore(
        index_name="{{config.configurable.vector_store_index_sparse}}",
        namespace="{{config.configurable.vector_store_namespace}}",
        client_kwargs={"api_key": "[[pinecone_api_key]]"},
    )

    dense_search = DenseSearchNode(
        name="dense_search",
        vector_store=dense_store,
        embedding_method="{{config.configurable.dense_embedding_method}}",
        top_k="{{config.configurable.dense_top_k}}",
        score_threshold="{{config.configurable.dense_similarity_threshold}}",
    )
    sparse_search = SparseSearchNode(
        name="sparse_search",
        vector_store=sparse_store,
        embedding_method="{{config.configurable.sparse_embedding_method}}",
        top_k="{{config.configurable.sparse_top_k}}",
        score_threshold="{{config.configurable.sparse_score_threshold}}",
        vector_store_candidate_k="{{config.configurable.sparse_vector_store_candidate_k}}",
    )
    web_search = WebSearchNode(
        name="web_search",
        provider="{{config.configurable.web_search_provider}}",
        api_key="[[tavily_api_key]]",
        max_results="{{config.configurable.web_search_max_results}}",
        search_depth="{{config.configurable.web_search_search_depth}}",
        include_raw_content=False,
    )
    retrieval_collector = RetrievalCollectorNode(name="retrieval_collector")
    fusion = HybridFusionNode(
        name="fusion",
        results_field="retrieval_collector",
        strategy="rrf",
        weights={"dense": 0.5, "sparse": 0.3, "web": 0.2},
        rrf_k="{{config.configurable.fusion_rrf_k}}",
        top_k="{{config.configurable.fusion_top_k}}",
    )
    reranker = PineconeRerankNode(
        name="reranker",
        source_result_key="fusion",
        results_field="results",
        model="{{config.configurable.reranker_model}}",
        rank_fields=["chunk_text"],
        top_n="{{config.configurable.reranker_top_n}}",
        return_documents=True,
        parameters={"truncate": "END"},
        client_kwargs={"api_key": "[[pinecone_api_key]]"},
        document_text_field="chunk_text",
        document_id_field="_id",
    )
    context_summarizer = ContextCompressorNode(
        name="context_summarizer",
        results_field="reranker",
        max_tokens="{{config.configurable.context_max_tokens}}",
        ai_model="{{config.configurable.context_summary_model}}",
        model_kwargs={"api_key": "[[openai_api_key]]"},
    )
    generator = GroundedGeneratorNode(
        name="generator",
        context_result_key="context_summarizer",
        context_field="original_results",
        ai_model="{{config.configurable.generation_model}}",
        model_kwargs={"api_key": "[[openai_api_key]]"},
        citation_style="inline",
    )
    citations = CitationsFormatterNode(
        name="citations",
        source_result_key="generator",
    )

    nodes = {
        "dense_search": dense_search,
        "sparse_search": sparse_search,
        "web_search": web_search,
        "retrieval_collector": retrieval_collector,
        "fusion": fusion,
        "reranker": reranker,
        "context_summarizer": context_summarizer,
        "generator": generator,
        "citations": citations,
    }

    workflow = StateGraph(State)
    for name, node in nodes.items():
        workflow.add_node(name, node)

    workflow.set_entry_point("dense_search")
    workflow.set_entry_point("sparse_search")
    workflow.set_entry_point("web_search")
    for source, dest in (
        ("dense_search", "retrieval_collector"),
        ("sparse_search", "retrieval_collector"),
        ("web_search", "retrieval_collector"),
        ("retrieval_collector", "fusion"),
        ("fusion", "reranker"),
        ("reranker", "context_summarizer"),
        ("context_summarizer", "generator"),
        ("generator", "citations"),
    ):
        workflow.add_edge(source, dest)
    workflow.add_edge("citations", END)

    return workflow
