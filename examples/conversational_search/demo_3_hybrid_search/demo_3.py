"""Hybrid search demo: retrieve + fuse over prebuilt Pinecone indexes."""

from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.embedding_registry import (
    OPENAI_TEXT_EMBEDDING_3_SMALL,
    PINECONE_BM25_DEFAULT,
)
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
from orcheo.nodes.conversational_search.vector_store import (
    BaseVectorStore,
    InMemoryVectorStore,
    PineconeVectorStore,
)


DEFAULT_CONFIG: dict[str, Any] = {
    "retrieval": {
        "dense": {
            "top_k": 8,
            "similarity_threshold": 0.0,
            "embedding_method": OPENAI_TEXT_EMBEDDING_3_SMALL,
        },
        "sparse": {
            "top_k": 10,
            "score_threshold": 0.0,
            "vector_store_candidate_k": 50,
            "embedding_method": PINECONE_BM25_DEFAULT,
        },
        "web_search": {
            "provider": "tavily",
            "api_key": "[[tavily_api_key]]",
            "max_results": 5,
            "search_depth": "advanced",
        },
        "fusion": {
            "strategy": "reciprocal_rank_fusion",
            "weights": {"dense": 0.5, "sparse": 0.3, "web": 0.2},
            "rrf_k": 60,
            "top_k": 8,
        },
        "context": {
            "max_tokens": 400,
            "summary_model": "openai:gpt-4o-mini",
            "model_kwargs": {"api_key": "[[openai_api_key]]"},
            "summary_prompt": (
                "Summarize the retrieved passages into a concise paragraph that cites "
                "the numbered sources in brackets."
            ),
        },
    },
    "vector_store": {
        "dense": {
            "type": "pinecone",
            "index_name": "orcheo-demo-dense",
            "namespace": "hybrid_search",
            "client_kwargs": {"api_key": "[[pinecone_api_key]]"},
        },
        "sparse": {
            "type": "pinecone",
            "index_name": "orcheo-demo-sparse",
            "namespace": "hybrid_search",
            "client_kwargs": {"api_key": "[[pinecone_api_key]]"},
        },
    },
    "reranker": {
        "model": "bge-reranker-v2-m3",
        "rank_fields": ["chunk_text"],
        "top_n": 10,
        "return_documents": True,
        "parameters": {"truncate": "END"},
        "client_kwargs": {"api_key": "[[pinecone_api_key]]"},
    },
    "generation": {
        "model": "openai:gpt-4o-mini",
        "model_kwargs": {"api_key": "[[openai_api_key]]"},
    },
}


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


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override values into the base configuration."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def configure_vector_stores(
    config: dict[str, Any] | None,
) -> dict[str, BaseVectorStore]:
    """Return vector store implementations for dense and sparse retrieval."""
    config = config or {}
    fallback_cfg: dict[str, Any] | None = None
    if any(key in config for key in ("type", "pinecone", "index_name")):
        fallback_cfg = config
    dense_cfg = config.get("dense") or fallback_cfg
    sparse_cfg = config.get("sparse") or fallback_cfg
    return {
        "dense": build_vector_store(dense_cfg),
        "sparse": build_vector_store(sparse_cfg),
    }


def build_vector_store(cfg: dict[str, Any] | None) -> BaseVectorStore:
    """Create a concrete vector store from the supplied configuration."""
    if not cfg:
        return InMemoryVectorStore()
    store_type = str(cfg.get("type", "pinecone")).lower()
    if store_type != "pinecone":
        return InMemoryVectorStore()
    pinecone_cfg = dict(cfg.get("pinecone") or {})
    if not pinecone_cfg:
        pinecone_cfg = {
            "index_name": cfg.get("index_name"),
            "namespace": cfg.get("namespace"),
            "client_kwargs": cfg.get("client_kwargs"),
        }
    index_name = pinecone_cfg.get("index_name")
    if not index_name:
        raise ValueError("Pinecone vector store config requires 'index_name'")
    client_kwargs = dict(pinecone_cfg.get("client_kwargs") or {})
    return PineconeVectorStore(
        index_name=index_name,
        namespace=pinecone_cfg.get("namespace"),
        client_kwargs=client_kwargs,
    )


async def build_graph(config: dict[str, Any] | None = None) -> StateGraph:
    """Assemble and return the hybrid search workflow graph."""
    merged_config = merge_dicts(DEFAULT_CONFIG, config or {})
    vector_store_cfg = merged_config.get("vector_store", {})
    vector_stores = configure_vector_stores(vector_store_cfg)

    retrieval_cfg = merged_config["retrieval"]
    dense_cfg = retrieval_cfg["dense"]
    sparse_cfg = retrieval_cfg["sparse"]
    web_cfg = retrieval_cfg["web_search"]
    fusion_cfg = retrieval_cfg["fusion"]
    context_cfg = retrieval_cfg["context"]
    generation_cfg = merged_config["generation"]

    nodes = {
        "dense_search": build_dense_search_node(dense_cfg, vector_stores["dense"]),
        "sparse_search": build_sparse_search_node(sparse_cfg, vector_stores["sparse"]),
        "web_search": build_web_search_node(web_cfg),
        "retrieval_collector": RetrievalCollectorNode(name="retrieval_collector"),
        "fusion": build_hybrid_fusion_node(fusion_cfg),
        "reranker": build_reranker_node(merged_config.get("reranker", {})),
        "context_summarizer": build_context_summarizer_node(context_cfg),
        "generator": build_generator_node(generation_cfg),
        "citations": CitationsFormatterNode(
            name="citations",
            source_result_key="generator",
        ),
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


def build_dense_search_node(
    cfg: dict[str, Any],
    vector_store: BaseVectorStore,
) -> DenseSearchNode:
    """Create the dense retrieval node with validated configuration."""
    embedding_method = cfg.get("embedding_method")
    if not embedding_method:
        raise ValueError("Dense retriever requires 'embedding_method' in the config")
    return DenseSearchNode(
        name="dense_search",
        vector_store=vector_store,
        embedding_method=embedding_method,
        top_k=cfg.get("top_k", 8),
        score_threshold=cfg.get("similarity_threshold", 0.0),
    )


def build_sparse_search_node(
    cfg: dict[str, Any],
    vector_store: BaseVectorStore,
) -> SparseSearchNode:
    """Create the sparse retrieval node with validated configuration."""
    embedding_method = cfg.get("embedding_method")
    if not embedding_method:
        raise ValueError("Sparse retriever requires 'embedding_method' in the config")
    return SparseSearchNode(
        name="sparse_search",
        top_k=cfg.get("top_k", 10),
        score_threshold=cfg.get("score_threshold", 0.0),
        vector_store=vector_store,
        embedding_method=embedding_method,
        vector_store_candidate_k=cfg.get("vector_store_candidate_k", 50),
    )


def build_web_search_node(cfg: dict[str, Any]) -> WebSearchNode:
    """Create the optional web search node."""
    return WebSearchNode(
        name="web_search",
        provider=cfg.get("provider", "tavily"),
        api_key=cfg.get("api_key"),
        max_results=cfg.get("max_results", 5),
        search_depth=cfg.get("search_depth", "basic"),
        days=cfg.get("days"),
        topic=cfg.get("topic"),
        include_domains=cfg.get("include_domains"),
        exclude_domains=cfg.get("exclude_domains"),
        include_raw_content=False,
    )


def build_hybrid_fusion_node(cfg: dict[str, Any]) -> HybridFusionNode:
    """Create the fusion node that merges retriever outputs."""
    strategy = cfg.get("strategy", "rrf")
    if strategy == "reciprocal_rank_fusion":
        strategy = "rrf"
    return HybridFusionNode(
        name="fusion",
        results_field="retrieval_collector",
        strategy=strategy,
        weights=cfg.get("weights", {}),
        rrf_k=cfg.get("rrf_k", 60),
        top_k=cfg.get("top_k", 8),
    )


def build_reranker_node(cfg: dict[str, Any]) -> PineconeRerankNode:
    """Create the reranker node using provided Pinecone settings."""
    return PineconeRerankNode(
        name="reranker",
        source_result_key="fusion",
        results_field="results",
        model=cfg.get("model", "bge-reranker-v2-m3"),
        rank_fields=cfg.get("rank_fields", ["chunk_text"]),
        top_n=cfg.get("top_n", 10),
        return_documents=cfg.get("return_documents", True),
        parameters=dict(cfg.get("parameters") or {}),
        client_kwargs=dict(cfg.get("client_kwargs") or {}),
        document_text_field=cfg.get("document_text_field", "chunk_text"),
        document_id_field=cfg.get("document_id_field", "_id"),
    )


def build_context_summarizer_node(cfg: dict[str, Any]) -> ContextCompressorNode:
    """Create the context summarizer node with its prompt configuration."""
    context_prompt = cfg.get(
        "summary_prompt",
        ContextCompressorNode.model_fields["summary_prompt"].default,  # type: ignore[index]
    )
    return ContextCompressorNode(
        name="context_summarizer",
        results_field="reranker",
        max_tokens=cfg.get("max_tokens", 400),
        ai_model=cfg.get("summary_model"),
        model_kwargs=cfg.get("model_kwargs", {}),
        summary_prompt=context_prompt,
    )


def build_generator_node(cfg: dict[str, Any]) -> GroundedGeneratorNode:
    """Create the grounded generator node."""
    return GroundedGeneratorNode(
        name="generator",
        context_result_key="context_summarizer",
        ai_model=cfg.get("model"),
        model_kwargs=cfg.get("model_kwargs", {}),
        citation_style="inline",
    )
