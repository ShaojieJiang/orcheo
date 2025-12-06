"""Hybrid search Demo 2.2: retrieve + fuse over prebuilt Pinecone indexes."""

import asyncio
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
    SparseSearchNode,
    WebSearchNode,
)
from orcheo.nodes.conversational_search.vector_store import (
    BaseVectorStore,
    InMemoryVectorStore,
    PineconeVectorStore,
)
from orcheo.runtime.credentials import CredentialResolver, credential_resolution


DEFAULT_CONFIG: dict[str, Any] = {
    "retrieval": {
        "dense": {"top_k": 8, "similarity_threshold": 0.0},
        "sparse": {
            "top_k": 10,
            "score_threshold": 0.0,
            "vector_store_candidate_k": 50,
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
        "type": "pinecone",
        "pinecone": {
            "index_name": "orcheo-demo",
            "namespace": "hybrid_search",
            "client_kwargs": {
                "api_key": "[[pinecone_api_key]]",
            },
        },
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

    async def run(self, state: State, _: RunnableConfig) -> dict[str, Any]:
        """Gather retriever outputs and ensure at least one result is present."""
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


def configure_vector_store(config: dict[str, Any] | None) -> BaseVectorStore:
    """Return a vector store implementation based on the provided configuration."""
    config = config or {}
    store_type = str(config.get("type", "pinecone")).lower()
    if store_type == "pinecone":
        pinecone_cfg = config.get("pinecone", {}) or {}
        client_kwargs = dict(pinecone_cfg.get("client_kwargs") or {})
        return PineconeVectorStore(
            index_name=pinecone_cfg.get("index_name", "orcheo-hybrid-demo"),
            namespace=pinecone_cfg.get("namespace"),
            client_kwargs=client_kwargs,
        )
    return InMemoryVectorStore()


async def build_graph(config: dict[str, Any] | None = None) -> StateGraph:
    """Assemble and return the hybrid search workflow graph."""
    merged_config = merge_dicts(DEFAULT_CONFIG, config or {})
    vector_store_cfg = merged_config.get("vector_store", {})
    vector_store = configure_vector_store(vector_store_cfg)

    retrieval_cfg = merged_config["retrieval"]
    dense_cfg = retrieval_cfg["dense"]
    sparse_cfg = retrieval_cfg["sparse"]
    web_cfg = retrieval_cfg["web_search"]
    fusion_cfg = retrieval_cfg["fusion"]
    context_cfg = retrieval_cfg["context"]
    generation_cfg = merged_config["generation"]

    dense_search = DenseSearchNode(
        name="dense_search",
        vector_store=vector_store,
        top_k=dense_cfg.get("top_k", 8),
        score_threshold=dense_cfg.get("similarity_threshold", 0.0),
    )

    sparse_search = SparseSearchNode(
        name="sparse_search",
        top_k=sparse_cfg.get("top_k", 10),
        score_threshold=sparse_cfg.get("score_threshold", 0.0),
        vector_store=vector_store,
        vector_store_candidate_k=sparse_cfg.get("vector_store_candidate_k", 50),
    )

    optional_web = WebSearchNode(
        name="web_search",
        provider=web_cfg.get("provider", "tavily"),
        api_key=web_cfg.get("api_key"),
        max_results=web_cfg.get("max_results", 5),
        search_depth=web_cfg.get("search_depth", "basic"),
        days=web_cfg.get("days"),
        topic=web_cfg.get("topic"),
        include_domains=web_cfg.get("include_domains"),
        exclude_domains=web_cfg.get("exclude_domains"),
        include_raw_content=False,
    )

    retriever_collector = RetrievalCollectorNode(name="retrieval_collector")

    strategy = fusion_cfg.get("strategy", "rrf")
    if strategy == "reciprocal_rank_fusion":
        strategy = "rrf"
    hybrid_fusion = HybridFusionNode(
        name="fusion",
        results_field="retrieval_collector",
        strategy=strategy,
        weights=fusion_cfg.get("weights", {}),
        rrf_k=fusion_cfg.get("rrf_k", 60),
        top_k=fusion_cfg.get("top_k", 8),
    )

    context_prompt = context_cfg.get(
        "summary_prompt",
        ContextCompressorNode.model_fields["summary_prompt"].default,  # type: ignore[index]
    )
    context_summarizer = ContextCompressorNode(
        name="context_summarizer",
        results_field="fusion",
        max_tokens=context_cfg.get("max_tokens", 400),
        ai_model=context_cfg.get("summary_model"),
        model_kwargs=context_cfg.get("model_kwargs", {}),
        summary_prompt=context_prompt,
    )

    generator = GroundedGeneratorNode(
        name="generator",
        context_result_key="context_summarizer",
        ai_model=generation_cfg.get("model"),
        model_kwargs=generation_cfg.get("model_kwargs", {}),
        citation_style="inline",
    )

    citations = CitationsFormatterNode(
        name="citations",
        source_result_key="generator",
    )

    workflow = StateGraph(State)
    workflow.add_node("dense_search", dense_search)
    workflow.add_node("sparse_search", sparse_search)
    workflow.add_node("web_search", optional_web)
    workflow.add_node("retrieval_collector", retriever_collector)
    workflow.add_node("fusion", hybrid_fusion)
    workflow.add_node("context_summarizer", context_summarizer)
    workflow.add_node("generator", generator)
    workflow.add_node("citations", citations)

    workflow.set_entry_point("dense_search")
    workflow.add_edge("dense_search", "sparse_search")
    workflow.add_edge("sparse_search", "web_search")
    workflow.add_edge("web_search", "retrieval_collector")
    workflow.add_edge("retrieval_collector", "fusion")
    workflow.add_edge("fusion", "context_summarizer")
    workflow.add_edge("context_summarizer", "generator")
    workflow.add_edge("generator", "citations")
    workflow.add_edge("citations", END)

    return workflow


def setup_credentials() -> CredentialResolver:
    """Set up the credential resolver."""
    from orcheo_backend.app.dependencies import get_vault

    vault = get_vault()
    return CredentialResolver(vault)


async def run_demo_2_2(
    config: dict[str, Any] | None = None,
    resolver: CredentialResolver | None = None,
) -> None:
    """Execute the compiled hybrid search workflow using provided credentials."""
    print("=== Demo 2.2: Hybrid Search ===")
    print(
        "This run assumes document indexes already exist in Pinecone and only "
        "exercises retrieval, fusion, and generation.\n"
    )

    resolver = resolver or setup_credentials()
    workflow = await build_graph(config)
    app = workflow.compile()

    query = "Find cases mentioning 'reasonable doubt' and mens rea"
    payload = {"inputs": {"message": query}}

    with credential_resolution(resolver):
        result = await app.ainvoke(payload)  # type: ignore[arg-type]

    generator_output = result.get("results", {}).get("generator", {})
    reply = generator_output.get("reply", "")
    citations_payload = result.get("results", {}).get("citations", {})

    print("Query:", query)
    print("\n--- Grounded Answer ---")
    print(reply[:500] + ("..." if len(reply) > 500 else ""))

    formatted = citations_payload.get("formatted", [])
    if formatted:
        print("\n--- Citations ---")
        for entry in formatted:
            print(f"- {entry}")
    print("\n=== End ===")


async def main() -> None:
    """Entrypoint used when invoking this demo as a standalone script."""
    resolver = setup_credentials()
    await run_demo_2_2(resolver=resolver)


if __name__ == "__main__":
    asyncio.run(main())
