"""Retrieval nodes for conversational search flows."""

from __future__ import annotations
import hashlib
import math
from collections import Counter
from collections.abc import Iterable
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import ConfigDict, Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.ingestion import EmbeddingFunction
from orcheo.nodes.conversational_search.models import (
    Document,
    DocumentChunk,
    SearchResult,
)
from orcheo.nodes.conversational_search.vector_store import (
    BaseVectorStore,
    InMemoryVectorStore,
)
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="VectorSearchNode",
        description="Perform dense retrieval against a vector store.",
        category="conversational_search",
    )
)
class VectorSearchNode(TaskNode):
    """Embed the query and retrieve similar chunks from a vector store."""

    query_key: str = Field(
        default="query",
        description="Key in ``state.inputs`` containing the query string.",
    )
    vector_store: BaseVectorStore = Field(
        default_factory=InMemoryVectorStore,
        description="Vector store adapter used for similarity search",
    )
    embedding_function: EmbeddingFunction | None = Field(
        default=None,
        description="Callable that converts queries to embedding vectors",
    )
    top_k: int = Field(default=10, gt=0, description="Maximum results to return")
    score_threshold: float = Field(
        default=0.0,
        description="Minimum score required to include a match",
    )
    filter_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata filters applied before scoring",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Embed the incoming query and return ranked vector matches."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = f"Missing or invalid query under inputs['{self.query_key}']"
            raise ValueError(msg)

        vector = (await self._embed([query.strip()]))[0]
        results = await self.vector_store.query(
            vector=vector,
            top_k=self.top_k,
            filter_metadata=self.filter_metadata or None,
        )
        filtered = [
            result for result in results if result.score >= self.score_threshold
        ]
        return {"results": filtered}

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        embedder = self.embedding_function or self._default_embedding_function
        result = embedder(texts)
        if hasattr(result, "__await__"):
            result = await result  # type: ignore[assignment]
        if not isinstance(result, list) or not all(
            isinstance(row, list) for row in result
        ):
            msg = "Embedding function must return List[List[float]]"
            raise ValueError(msg)
        return result

    @staticmethod
    def _default_embedding_function(texts: list[str]) -> list[list[float]]:
        """Deterministic fallback embedding using SHA256 hashing."""
        embeddings: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vector = [byte / 255.0 for byte in digest[:16]]
            embeddings.append(vector)
        return embeddings


@registry.register(
    NodeMetadata(
        name="BM25SearchNode",
        description="Execute BM25 keyword search over a local corpus.",
        category="conversational_search",
    )
)
class BM25SearchNode(TaskNode):
    """Lightweight BM25 implementation for chunk/document retrieval."""

    query_key: str = Field(
        default="query",
        description="Key in ``state.inputs`` containing the query string.",
    )
    source_result_key: str | None = Field(
        default=None,
        description=(
            "Optional key in ``state.results`` that contains the corpus payload."
        ),
    )
    documents_field: str = Field(
        default="chunks",
        description="Field name within results holding documents or chunks to search.",
    )
    top_k: int = Field(default=10, gt=0, description="Maximum results to return")
    score_threshold: float = Field(
        default=0.0,
        description="Minimum score required to include a match",
    )
    k1: float = Field(default=1.5, gt=0, description="BM25 term frequency scaling")
    b: float = Field(
        default=0.75, ge=0, description="BM25 length normalization parameter"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Score corpus entries against the query using BM25."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = f"Missing or invalid query under inputs['{self.query_key}']"
            raise ValueError(msg)

        corpus = self._resolve_corpus(state)
        if not corpus:
            return {"results": []}

        tokens = self._tokenize(query)
        doc_tokens = [self._tokenize(item[1]) for item in corpus]
        scores = self._bm25_scores(tokens, doc_tokens)

        results: list[SearchResult] = []
        for (doc_id, content, metadata), score in zip(corpus, scores, strict=True):
            if score < self.score_threshold:
                continue
            results.append(
                SearchResult(
                    id=doc_id,
                    content=content,
                    metadata=metadata,
                    score=score,
                    source="bm25",
                    sources=["bm25"],
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return {"results": results[: self.top_k]}

    def _resolve_corpus(self, state: State) -> list[tuple[str, str, dict[str, Any]]]:
        results = state.get("results", {})
        payload: Any
        if self.source_result_key:
            source = results.get(self.source_result_key, {})
            if isinstance(source, dict) and self.documents_field in source:
                payload = source[self.documents_field]
            else:
                payload = (
                    results.get(self.documents_field) if source is None else source
                )
        else:
            payload = results.get(self.documents_field)
        if payload is None:
            return []
        if not isinstance(payload, list):
            msg = f"{self.documents_field} payload must be a list"
            raise ValueError(msg)

        corpus: list[tuple[str, str, dict[str, Any]]] = []
        for index, item in enumerate(payload):
            doc_id, content, metadata = self._coerce_item(item, index)
            corpus.append((doc_id, content, metadata))
        return corpus

    @staticmethod
    def _coerce_item(item: Any, index: int) -> tuple[str, str, dict[str, Any]]:
        if isinstance(item, DocumentChunk):
            return item.id, item.content, item.metadata
        if isinstance(item, Document):
            return item.id, item.content, item.metadata
        if isinstance(item, dict):
            if "content" not in item:
                msg = "Corpus entries must include 'content'"
                raise ValueError(msg)
            doc_id = item.get("id") or f"doc-{index}"
            metadata = item.get("metadata") or {}
            return doc_id, str(item["content"]), dict(metadata)
        if isinstance(item, str):
            return f"doc-{index}", item, {}
        msg = "Unsupported corpus entry type"
        raise ValueError(msg)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [token for token in text.lower().split() if token]

    def _bm25_scores(
        self, query_tokens: list[str], corpus_tokens: list[list[str]]
    ) -> list[float]:
        doc_freq: Counter[str] = Counter()
        for tokens in corpus_tokens:
            doc_freq.update(set(tokens))
        num_docs = len(corpus_tokens)
        avgdl = sum(len(tokens) for tokens in corpus_tokens) / max(num_docs, 1)

        scores: list[float] = []
        for tokens in corpus_tokens:
            tf = Counter(tokens)
            doc_len = len(tokens) or 1
            score = 0.0
            for term in query_tokens:
                if term not in tf:
                    continue
                numerator = num_docs - doc_freq[term] + 0.5
                denominator = doc_freq[term] + 0.5
                idf = math.log(numerator / denominator + 1)
                numerator = tf[term] * (self.k1 + 1)
                normalization = 1 - self.b + self.b * doc_len / avgdl
                denominator = tf[term] + self.k1 * normalization
                score += idf * numerator / denominator
            scores.append(score)
        return scores


@registry.register(
    NodeMetadata(
        name="HybridFusionNode",
        description="Fuse multiple retrieval result sets via RRF or weighted sum.",
        category="conversational_search",
    )
)
class HybridFusionNode(TaskNode):
    """Combine retrieval outputs from dense and sparse backends."""

    source_result_keys: list[str] = Field(
        default_factory=lambda: ["vector_search", "bm25_search"],
        description="Result keys to fuse from ``state.results``.",
    )
    strategy: str = Field(
        default="rrf",
        description="Fusion strategy: 'rrf' or 'weighted_sum'",
    )
    weights: dict[str, float] = Field(
        default_factory=dict,
        description="Optional weights keyed by result source",
    )
    rrf_k: int = Field(default=60, gt=0, description="RRF k parameter")
    top_k: int = Field(default=10, gt=0, description="Maximum fused results to return")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Fuse retrieval outputs using reciprocal rank or weighted scores."""
        collected = self._collect_results(state)
        if not collected:
            msg = "HybridFusionNode requires at least one retrieval result set"
            raise ValueError(msg)

        fused = self._reciprocal_rank_fusion(collected)
        if self.strategy == "weighted_sum":
            fused = self._weighted_sum_fusion(collected)

        fused.sort(key=lambda item: item.score, reverse=True)
        return {"results": fused[: self.top_k]}

    def _collect_results(self, state: State) -> dict[str, list[SearchResult]]:
        aggregated: dict[str, list[SearchResult]] = {}
        results = state.get("results", {})
        for key in self.source_result_keys:
            payload = results.get(key)
            if payload is None:
                continue
            entries: Iterable[Any]
            if isinstance(payload, dict) and "results" in payload:
                entries = payload["results"]
            elif isinstance(payload, list):
                entries = payload
            else:
                continue
            aggregated[key] = [SearchResult.model_validate(item) for item in entries]
        return aggregated

    def _reciprocal_rank_fusion(
        self, collected: dict[str, list[SearchResult]]
    ) -> list[SearchResult]:
        fused: dict[str, SearchResult] = {}
        scores: dict[str, float] = {}
        for source, results in collected.items():
            for rank, result in enumerate(results, start=1):
                fused.setdefault(result.id, result)
                scores.setdefault(result.id, 0.0)
                scores[result.id] += 1 / (self.rrf_k + rank)
                merged_sources = set(fused[result.id].sources or [])
                merged_sources.update(result.sources or [source])
                fused[result.id] = fused[result.id].model_copy(
                    update={
                        "sources": sorted(merged_sources),
                        "source": fused[result.id].source or source,
                    }
                )
        return [
            fused[result_id].model_copy(update={"score": score})
            for result_id, score in scores.items()
        ]

    def _weighted_sum_fusion(
        self, collected: dict[str, list[SearchResult]]
    ) -> list[SearchResult]:
        fused: dict[str, SearchResult] = {}
        scores: dict[str, float] = {}
        for source, results in collected.items():
            weight = self.weights.get(source, 1.0)
            for result in results:
                fused.setdefault(result.id, result)
                scores.setdefault(result.id, 0.0)
                scores[result.id] += weight * result.score
                merged_sources = set(fused[result.id].sources or [])
                merged_sources.update(result.sources or [source])
                fused[result.id] = fused[result.id].model_copy(
                    update={
                        "sources": sorted(merged_sources),
                        "source": fused[result.id].source or source,
                    }
                )
        return [
            fused[result_id].model_copy(update={"score": score})
            for result_id, score in scores.items()
        ]
