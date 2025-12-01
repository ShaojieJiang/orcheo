"""Hybrid search demo showcasing dense, sparse, and web retrieval fusion."""

from __future__ import annotations
from pathlib import Path
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
from orcheo.nodes.conversational_search.ingestion import (
    deterministic_embedding_function,
)
from orcheo.nodes.conversational_search.models import DocumentChunk, VectorRecord
from orcheo.nodes.conversational_search.query_processing import ContextCompressorNode
from orcheo.nodes.conversational_search.retrieval import (
    BM25SearchNode,
    HybridFusionNode,
    ReRankerNode,
    VectorSearchNode,
    WebSearchNode,
)
from orcheo.nodes.conversational_search.vector_store import InMemoryVectorStore
from orcheo.runtime.credentials import CredentialResolver, credential_resolution


def _default_docs_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "data" / "docs")


# Default configuration inlined for server execution
DEFAULT_CONFIG: dict[str, Any] = {
    "corpus": {
        "docs_path": _default_docs_path(),
        "chunk_size": 600,
        "chunk_overlap": 80,
    },
    "retrieval": {
        "vector": {"top_k": 8, "similarity_threshold": 0.0},
        "bm25": {"top_k": 10, "score_threshold": 0.0},
        "web_search": {"max_results": 5, "search_depth": "advanced"},
        "fusion": {
            "strategy": "reciprocal_rank_fusion",
            "weights": {"vector": 0.5, "bm25": 0.3, "web": 0.2},
            "rrf_k": 60,
            "top_k": 8,
        },
        "reranker": {"top_k": 5, "length_penalty": 0.0005},
        "context": {"max_tokens": 2000},
    },
    "generation": {
        "model": "openai:gpt-4o-mini",
        "model_kwargs": {"api_key": "[[openai_api_key]]"},
    },
}


def _infer_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        candidate = line.strip()
        if candidate:
            return candidate
    return fallback


class HybridCorpusPreparer:
    """Loads the local markdown corpus and prepares dense + sparse artifacts."""

    def __init__(self, docs_path: str, chunk_size: int, chunk_overlap: int) -> None:
        """Initialize the corpus preparer."""
        self.docs_path = Path(docs_path)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._chunks_cache: list[DocumentChunk] | None = None

    def load_chunks(self) -> list[DocumentChunk]:
        """Return cached chunks, computing them on first access."""
        if self._chunks_cache is None:
            self._chunks_cache = self._build_chunks()
        return [chunk.model_copy(deep=True) for chunk in self._chunks_cache]

    def build_vector_store(self) -> InMemoryVectorStore:
        """Populate an in-memory vector store with deterministic embeddings."""
        vector_store = InMemoryVectorStore()
        chunks = self.load_chunks()
        embeddings = deterministic_embedding_function(
            [chunk.content for chunk in chunks]
        )

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            vector_store.records[chunk.id] = VectorRecord(
                id=chunk.id,
                values=embedding,
                text=chunk.content,
                metadata=chunk.metadata,
            )
        return vector_store

    def _build_chunks(self) -> list[DocumentChunk]:
        docs_dir = self.docs_path
        if not docs_dir.exists():
            msg = f"Corpus directory not found: {docs_dir}"
            raise FileNotFoundError(msg)

        chunks: list[DocumentChunk] = []
        for path in sorted(docs_dir.glob("*.md")):
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                continue
            document_id = path.stem
            title = _infer_title(
                content, fallback=document_id.replace("_", " ").title()
            )
            start = 0
            chunk_index = 0
            while start < len(content):
                end = min(start + self.chunk_size, len(content))
                chunk_text = content[start:end].strip()
                if not chunk_text:
                    break
                chunk_id = f"{document_id}-chunk-{chunk_index}"
                metadata = {
                    "document_id": document_id,
                    "chunk_index": chunk_index,
                    "source": path.name,
                    "title": title,
                    "demo": "hybrid_search",
                }
                chunks.append(
                    DocumentChunk(
                        id=chunk_id,
                        document_id=document_id,
                        index=chunk_index,
                        content=chunk_text,
                        metadata=metadata,
                    )
                )
                if end == len(content):
                    break
                start = end - self.chunk_overlap
                chunk_index += 1

        if not chunks:
            msg = f"No markdown documents found in {docs_dir}"
            raise ValueError(msg)
        return chunks


class CorpusBootstrapNode(TaskNode):
    """Inject a pre-chunked corpus into the graph state."""

    chunks: list[DocumentChunk] = Field(default_factory=list)

    async def run(self, _: State, __: RunnableConfig) -> dict[str, Any]:
        """Provide chunks for downstream BM25 search."""
        cloned = [chunk.model_copy(deep=True) for chunk in self.chunks]
        return {"chunks": cloned, "chunk_count": len(cloned)}


def _default_retriever_map() -> dict[str, str]:
    return {"vector": "vector_search", "bm25": "bm25_search", "web": "web_search"}


class RetrievalCollectorNode(TaskNode):
    """Collect outputs from multiple retrievers for hybrid fusion."""

    retriever_map: dict[str, str] = Field(default_factory=_default_retriever_map)

    async def run(self, state: State, _: RunnableConfig) -> dict[str, Any]:
        """Merge retriever outputs keyed by logical source name."""
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


class OptionalWebSearchNode(WebSearchNode):
    """Web search node that can gracefully fall back when Tavily is unavailable."""

    suppress_errors: bool = Field(
        default=True,
        description="Return empty results instead of raising when Tavily is missing.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Run Tavily search, optionally suppressing failures."""
        try:
            return await super().run(state, config)
        except ValueError as exc:
            if not self.suppress_errors:
                raise
            return {"results": [], "warning": str(exc), "source": self.source_name}
        except Exception as exc:  # pragma: no cover - network/runtime guard
            if not self.suppress_errors:
                raise
            return {
                "results": [],
                "warning": f"web search unavailable: {exc!s}",
                "source": self.source_name,
            }


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


async def build_graph(config: dict[str, Any] | None = None) -> StateGraph:
    """Entrypoint for the Orcheo server to load the hybrid search graph."""
    merged_config = _merge_dicts(DEFAULT_CONFIG, config or {})
    corpus_cfg = merged_config["corpus"]
    preparer = HybridCorpusPreparer(
        docs_path=corpus_cfg["docs_path"],
        chunk_size=corpus_cfg.get("chunk_size", 600),
        chunk_overlap=corpus_cfg.get("chunk_overlap", 80),
    )
    chunks = preparer.load_chunks()
    vector_store = preparer.build_vector_store()

    vector_cfg = merged_config["retrieval"]["vector"]
    bm25_cfg = merged_config["retrieval"]["bm25"]
    web_cfg = merged_config["retrieval"]["web_search"]
    fusion_cfg = merged_config["retrieval"]["fusion"]
    reranker_cfg = merged_config["retrieval"]["reranker"]
    context_cfg = merged_config["retrieval"]["context"]
    generation_cfg = merged_config["generation"]

    corpus_loader = CorpusBootstrapNode(name="corpus_bootstrap", chunks=chunks)

    vector_search = VectorSearchNode(
        name="vector_search",
        vector_store=vector_store,
        top_k=vector_cfg.get("top_k", 8),
        score_threshold=vector_cfg.get("similarity_threshold", 0.0),
        source_name="vector",
    )

    bm25_search = BM25SearchNode(
        name="bm25_search",
        source_result_key="corpus_bootstrap",
        chunks_field="chunks",
        top_k=bm25_cfg.get("top_k", 10),
        score_threshold=bm25_cfg.get("score_threshold", 0.0),
        source_name="bm25",
    )

    optional_web = OptionalWebSearchNode(
        name="web_search",
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

    reranker = ReRankerNode(
        name="reranker",
        source_result_key="fusion",
        top_k=reranker_cfg.get("top_k", 5),
        length_penalty=reranker_cfg.get("length_penalty", 0.0),
    )

    context = ContextCompressorNode(
        name="context_compressor",
        results_field="reranker",
        max_tokens=context_cfg.get("max_tokens", 2000),
    )

    generator = GroundedGeneratorNode(
        name="generator",
        context_result_key="context_compressor",
        ai_model=generation_cfg.get("model"),
        model_kwargs=generation_cfg.get("model_kwargs", {}),
        citation_style="inline",
    )

    citations = CitationsFormatterNode(
        name="citations",
        source_result_key="generator",
    )

    workflow = StateGraph(State)
    workflow.add_node("corpus_bootstrap", corpus_loader)
    workflow.add_node("vector_search", vector_search)
    workflow.add_node("bm25_search", bm25_search)
    workflow.add_node("web_search", optional_web)
    workflow.add_node("retrieval_collector", retriever_collector)
    workflow.add_node("fusion", hybrid_fusion)
    workflow.add_node("reranker", reranker)
    workflow.add_node("context_compressor", context)
    workflow.add_node("generator", generator)
    workflow.add_node("citations", citations)

    workflow.set_entry_point("corpus_bootstrap")
    workflow.add_edge("corpus_bootstrap", "vector_search")
    workflow.add_edge("vector_search", "bm25_search")
    workflow.add_edge("bm25_search", "web_search")
    workflow.add_edge("web_search", "retrieval_collector")
    workflow.add_edge("retrieval_collector", "fusion")
    workflow.add_edge("fusion", "reranker")
    workflow.add_edge("reranker", "context_compressor")
    workflow.add_edge("context_compressor", "generator")
    workflow.add_edge("generator", "citations")
    workflow.add_edge("citations", END)

    return workflow


def setup_credentials() -> CredentialResolver:
    """Construct a credential resolver for OpenAI + Tavily usage."""
    from orcheo_backend.app.dependencies import get_vault

    vault = get_vault()
    return CredentialResolver(vault)


async def run_demo() -> None:
    """Run the hybrid search demo with a representative legal-style query."""
    print("=== Demo 2: Hybrid Search ===")
    print("This run fans queries out to vector, BM25, and Tavily before fusion.\n")

    resolver = setup_credentials()
    workflow = await build_graph()
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


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_demo())
