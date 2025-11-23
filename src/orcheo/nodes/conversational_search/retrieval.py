"""Retrieval primitives for conversational search."""

from __future__ import annotations
import inspect
import math
import re
from collections import defaultdict
from collections.abc import Callable
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field, field_validator
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.ingestion import EmbeddingIndexerNode
from orcheo.nodes.conversational_search.models import (
    DocumentChunk,
    FusedSearchResult,
    SearchResult,
)
from orcheo.nodes.conversational_search.vector_store import (
    BaseVectorStore,
    InMemoryVectorStore,
)
from orcheo.nodes.registry import NodeMetadata, registry


EmbeddingFunction = Callable[[list[str]], list[list[float]]]


@registry.register(
    NodeMetadata(
        name="VectorSearchNode",
        description="Execute dense vector similarity search using a vector store.",
        category="conversational_search",
    )
)
class VectorSearchNode(TaskNode):
    """Node that performs dense similarity search over an indexed corpus."""

    input_query_key: str = Field(
        default="query",
        description="Key within ``state.inputs`` containing the query.",
    )
    filter_key: str | None = Field(
        default="filters",
        description="Optional key within ``state.inputs`` containing metadata filters.",
    )
    vector_store: BaseVectorStore = Field(
        default_factory=InMemoryVectorStore,
        description="Vector store adapter used to perform similarity search.",
    )
    embedding_function: EmbeddingFunction | None = Field(
        default=None,
        description="Callable that converts the query string into an embedding vector.",
    )
    top_k: int = Field(default=5, gt=0, description="Number of results to return.")
    score_threshold: float = Field(
        default=0.0, ge=0.0, description="Minimum relevance score to keep a match."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Embed the query and execute similarity search against the vector store."""
        query = self._resolve_query(state)
        filters = self._resolve_filters(state)

        query_embedding = await self._embed_query(query)
        matches = await self.vector_store.search(
            query_embedding, top_k=self.top_k, filter_metadata=filters
        )

        filtered = [match for match in matches if match.score >= self.score_threshold]
        return {"matches": filtered}

    async def _embed_query(self, query: str) -> list[float]:
        embedder = (
            self.embedding_function or EmbeddingIndexerNode._default_embedding_function
        )
        result = embedder([query])
        if inspect.isawaitable(result):
            result = await result
        if (
            not isinstance(result, list)
            or not result
            or not isinstance(result[0], list)
        ):
            msg = "Embedding function must return List[List[float]]"
            raise ValueError(msg)
        return result[0]

    def _resolve_query(self, state: State) -> str:
        query = state.get("inputs", {}).get(self.input_query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "VectorSearchNode requires a non-empty string query"
            raise ValueError(msg)
        return query

    def _resolve_filters(self, state: State) -> dict[str, Any] | None:
        if self.filter_key is None:
            return None
        filters = state.get("inputs", {}).get(self.filter_key)
        if filters is None:
            return None
        if not isinstance(filters, dict):
            msg = "filters payload must be a mapping"
            raise ValueError(msg)
        return filters


@registry.register(
    NodeMetadata(
        name="BM25SearchNode",
        description="Perform BM25 search over in-memory chunk payloads.",
        category="conversational_search",
    )
)
class BM25SearchNode(TaskNode):
    """Node implementing a lightweight BM25 scorer over document chunks."""

    source_result_key: str = Field(
        default="chunking_strategy",
        description="Name of the upstream result entry containing chunks.",
    )
    chunks_field: str = Field(
        default="chunks",
        description="Field name within upstream results holding chunks.",
    )
    top_k: int = Field(default=5, gt=0, description="Number of results to return.")
    k1: float = Field(
        default=1.5, gt=0, description="BM25 term frequency scaling factor."
    )
    b: float = Field(
        default=0.75, ge=0.0, le=1.0, description="BM25 length normalization parameter."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Score chunks using BM25 and return the top ``top_k`` hits."""
        query = state.get("inputs", {}).get("query")
        if not isinstance(query, str) or not query.strip():
            msg = "BM25SearchNode requires a non-empty string query"
            raise ValueError(msg)

        chunks = self._resolve_chunks(state)
        if not chunks:
            msg = "BM25SearchNode requires at least one chunk"
            raise ValueError(msg)

        query_terms = self._tokenize(query)
        if not query_terms:
            msg = "Query must contain at least one token"
            raise ValueError(msg)

        index = [self._tokenize(chunk.content) for chunk in chunks]
        doc_freqs: dict[str, int] = defaultdict(int)
        for tokens in index:
            for term in set(tokens):
                doc_freqs[term] += 1

        avg_length = sum(len(tokens) for tokens in index) / len(index)
        scores: list[tuple[float, DocumentChunk]] = []
        for tokens, chunk in zip(index, chunks, strict=True):
            tf: dict[str, int] = defaultdict(int)
            for term in tokens:
                tf[term] += 1

            score = 0.0
            for term in query_terms:
                freq = tf.get(term, 0)
                if freq == 0:
                    continue
                doc_freq = doc_freqs.get(term, 0)
                idf = self._idf(term, len(index), doc_freq)
                numerator = freq * (self.k1 + 1)
                denominator = freq + self.k1 * (
                    1 - self.b + self.b * len(tokens) / avg_length
                )
                score += idf * numerator / denominator
            scores.append((score, chunk))

        scored = [
            SearchResult(
                id=chunk.id,
                score=score,
                text=chunk.content,
                metadata=chunk.metadata,
                source="bm25",
            )
            for score, chunk in scores
        ]
        scored.sort(key=lambda item: item.score, reverse=True)
        return {"matches": scored[: self.top_k]}

    def _resolve_chunks(self, state: State) -> list[DocumentChunk]:
        results = state.get("results", {})
        source = results.get(self.source_result_key, {})
        if isinstance(source, dict) and self.chunks_field in source:
            chunks = source[self.chunks_field]
        else:
            chunks = results.get(self.chunks_field)
        if not chunks:
            return []
        if not isinstance(chunks, list):
            msg = "chunks payload must be a list"
            raise ValueError(msg)
        return [DocumentChunk.model_validate(chunk) for chunk in chunks]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[\w']+", text.lower())

    def _idf(self, term: str, corpus_size: int, doc_freq: int) -> float:
        return math.log(1 + (corpus_size - doc_freq + 0.5) / (doc_freq + 0.5))


@registry.register(
    NodeMetadata(
        name="HybridFusionNode",
        description="Fuse multiple retriever outputs using RRF or weighted strategies.",
        category="conversational_search",
    )
)
class HybridFusionNode(TaskNode):
    """Node that combines retriever outputs via reciprocal-rank or weighted fusion."""

    source_keys: list[str] = Field(
        default_factory=lambda: ["vector_search", "bm25_search"],
        description="Names of upstream result entries to fuse.",
    )
    results_field: str = Field(
        default="matches",
        description="Field within each upstream result containing search matches.",
    )
    strategy: str = Field(
        default="rrf",
        description="Fusion strategy to apply. Supported: 'rrf', 'weighted_sum'.",
    )
    rrf_k: int = Field(default=60, gt=0, description="Rank smoothing constant for RRF.")
    weights: dict[str, float] = Field(
        default_factory=dict, description="Per-retriever weights for weighted_sum."
    )
    top_k: int = Field(
        default=10, gt=0, description="Number of fused results to return."
    )

    @field_validator("strategy")
    @classmethod
    def _validate_strategy(cls, value: str) -> str:
        if value not in {"rrf", "weighted_sum"}:
            msg = "strategy must be one of {'rrf', 'weighted_sum'}"
            raise ValueError(msg)
        return value

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Fuse upstream retrieval results using the configured strategy."""
        payloads = self._collect_payloads(state)
        fused: list[FusedSearchResult]
        if self.strategy == "rrf":
            fused = self._rrf(payloads)
        else:
            fused = self._weighted_sum(payloads)

        fused.sort(key=lambda item: item.score, reverse=True)
        return {"fused_results": fused[: self.top_k]}

    def _collect_payloads(self, state: State) -> dict[str, list[SearchResult]]:
        results = state.get("results", {})
        payloads: dict[str, list[SearchResult]] = {}
        for key in self.source_keys:
            data = results.get(key, {})
            if not isinstance(data, dict):
                continue
            matches = data.get(self.results_field) or data.get("matches")
            if not matches:
                continue
            payloads[key] = [SearchResult.model_validate(match) for match in matches]
        return payloads

    def _rrf(self, payloads: dict[str, list[SearchResult]]) -> list[FusedSearchResult]:
        scores: dict[str, FusedSearchResult] = {}
        for source, matches in payloads.items():
            for rank, match in enumerate(matches, start=1):
                contribution = 1 / (self.rrf_k + rank)
                current = scores.get(match.id)
                if current is None:
                    data = match.model_dump(exclude={"score", "source"})
                    current = FusedSearchResult(**data, score=0.0, sources=[source])
                    scores[match.id] = current
                else:
                    current.sources.append(source)
                current.score += contribution
        return list(scores.values())

    def _weighted_sum(
        self, payloads: dict[str, list[SearchResult]]
    ) -> list[FusedSearchResult]:
        scores: dict[str, FusedSearchResult] = {}
        for source, matches in payloads.items():
            weight = self.weights.get(source, 1.0)
            for match in matches:
                current = scores.get(match.id)
                if current is None:
                    data = match.model_dump(exclude={"score", "source"})
                    current = FusedSearchResult(**data, score=0.0, sources=[source])
                    scores[match.id] = current
                else:
                    current.sources.append(source)
                current.score += match.score * weight
        return list(scores.values())
