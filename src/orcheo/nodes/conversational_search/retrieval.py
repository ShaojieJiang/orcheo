"""Retrieval nodes for conversational search workflows."""

from __future__ import annotations
import inspect
import math
from collections import defaultdict
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.ingestion import (
    EmbeddingFunction,
    deterministic_embedding_function,
)
from orcheo.nodes.conversational_search.models import (
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
        description="Perform dense similarity search using a configured vector store.",
        category="conversational_search",
    )
)
class VectorSearchNode(TaskNode):
    """Node that performs dense retrieval against a vector store."""

    query_key: str = Field(
        default="query",
        description="Key within ``state.inputs`` containing the user query string.",
    )
    vector_store: BaseVectorStore = Field(
        default_factory=InMemoryVectorStore,
        description="Vector store adapter that will be queried.",
    )
    embedding_function: EmbeddingFunction | None = Field(
        default=None,
        description="Callable that embeds the query into a vector for retrieval.",
    )
    top_k: int = Field(
        default=5, gt=0, description="Maximum number of results to return"
    )
    score_threshold: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum score required for a result to be returned.",
    )
    filter_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata filters applied to the vector store query.",
    )
    source_name: str = Field(
        default="vector",
        description="Label used to annotate the originating retriever",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Embed the query and perform similarity search."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "VectorSearchNode requires a non-empty query string"
            raise ValueError(msg)

        embeddings = await self._embed([query])
        results = await self.vector_store.search(
            query=embeddings[0],
            top_k=self.top_k,
            filter_metadata=self.filter_metadata or None,
        )

        normalized = [
            SearchResult(
                id=result.id,
                score=result.score,
                text=result.text,
                metadata=result.metadata,
                source=result.source or self.source_name,
                sources=result.sources or [result.source or self.source_name],
            )
            for result in results
            if result.score >= self.score_threshold
        ]

        return {"results": normalized}

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        embedder = self.embedding_function or deterministic_embedding_function
        output = embedder(texts)
        if inspect.isawaitable(output):
            output = await output  # type: ignore[assignment]
        if not isinstance(output, list) or not all(
            isinstance(row, list) for row in output
        ):
            msg = "Embedding function must return List[List[float]]"
            raise ValueError(msg)
        return output


@registry.register(
    NodeMetadata(
        name="BM25SearchNode",
        description="Perform sparse keyword retrieval using BM25 scoring.",
        category="conversational_search",
    )
)
class BM25SearchNode(TaskNode):
    """Node that computes BM25 scores over in-memory chunks."""

    source_result_key: str = Field(
        default="chunking_strategy",
        description="Name of the upstream result containing chunks.",
    )
    chunks_field: str = Field(
        default="chunks", description="Field containing chunk payloads"
    )
    query_key: str = Field(
        default="query", description="Key within inputs holding the user query"
    )
    top_k: int = Field(
        default=5, gt=0, description="Maximum number of results to return"
    )
    score_threshold: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum BM25 score required for inclusion",
    )
    k1: float = Field(default=1.5, gt=0)
    b: float = Field(default=0.75, ge=0.0, le=1.0)
    source_name: str = Field(
        default="bm25", description="Label for the sparse retriever"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Score document chunks with BM25 and return the top matches."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "BM25SearchNode requires a non-empty query string"
            raise ValueError(msg)

        chunks = self._resolve_chunks(state)
        if not chunks:
            msg = "BM25SearchNode requires at least one chunk to search"
            raise ValueError(msg)

        tokenized_corpus = [self._tokenize(chunk.content) for chunk in chunks]
        avg_length = sum(len(doc) for doc in tokenized_corpus) / len(tokenized_corpus)

        scores: list[tuple[DocumentChunk, float]] = []
        query_tokens = self._tokenize(query)
        for chunk, tokens in zip(chunks, tokenized_corpus, strict=True):
            score = self._bm25_score(tokens, query_tokens, tokenized_corpus, avg_length)
            scores.append((chunk, score))

        ranked = [
            SearchResult(
                id=chunk.id,
                score=score,
                text=chunk.content,
                metadata=chunk.metadata,
                source=self.source_name,
                sources=[self.source_name],
            )
            for chunk, score in sorted(scores, key=lambda item: item[1], reverse=True)
            if score >= self.score_threshold
        ][: self.top_k]

        return {"results": ranked}

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

    def _bm25_score(
        self,
        document_tokens: list[str],
        query_tokens: list[str],
        corpus: list[list[str]],
        avg_length: float,
    ) -> float:
        score = 0.0
        doc_len = len(document_tokens)
        token_freq: dict[str, int] = defaultdict(int)
        for token in document_tokens:
            token_freq[token] += 1

        for token in query_tokens:
            idf = self._idf(token, corpus)
            freq = token_freq.get(token, 0)
            numerator = freq * (self.k1 + 1)
            denominator = freq + self.k1 * (
                1 - self.b + self.b * (doc_len / avg_length)
            )
            if denominator == 0:
                continue
            score += idf * (numerator / denominator)
        return score

    @staticmethod
    def _idf(token: str, corpus: list[list[str]]) -> float:
        doc_count = sum(1 for document in corpus if token in document)
        return math.log(((len(corpus) - doc_count + 0.5) / (doc_count + 0.5)) + 1)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [token for token in text.lower().split() if token]


@registry.register(
    NodeMetadata(
        name="HybridFusionNode",
        description="Fuse results from multiple retrievers using RRF or weighted sum.",
        category="conversational_search",
    )
)
class HybridFusionNode(TaskNode):
    """Merge retrieval results using Reciprocal Rank Fusion or weighted scores."""

    results_field: str = Field(
        default="retrieval_results",
        description="Key within results containing retriever outputs to fuse.",
    )
    strategy: str = Field(
        default="rrf",
        description="Fusion strategy: either 'rrf' or 'weighted_sum'.",
    )
    weights: dict[str, float] = Field(
        default_factory=dict,
        description="Optional per-retriever weights for weighted_sum fusion.",
    )
    rrf_k: int = Field(
        default=60, gt=0, description="RRF constant to dampen rank impact"
    )
    top_k: int = Field(
        default=10, gt=0, description="Number of fused results to return"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Fuse retriever outputs according to the configured strategy."""
        results_map = state.get("results", {}).get(self.results_field)
        if not isinstance(results_map, dict) or not results_map:
            msg = "HybridFusionNode requires a mapping of retriever results"
            raise ValueError(msg)

        if self.strategy not in {"rrf", "weighted_sum"}:
            msg = "strategy must be either 'rrf' or 'weighted_sum'"
            raise ValueError(msg)

        normalized: dict[str, list[SearchResult]] = {}
        for source, payload in results_map.items():
            if isinstance(payload, dict) and "results" in payload:
                entries = payload["results"]
            else:
                entries = payload
            if not isinstance(entries, list):
                msg = f"Retriever results for {source} must be a list"
                raise ValueError(msg)
            normalized[source] = [SearchResult.model_validate(item) for item in entries]

        fused = (
            self._reciprocal_rank_fusion(normalized)
            if self.strategy == "rrf"
            else self._weighted_sum_fusion(normalized)
        )

        ranked = sorted(fused.values(), key=lambda item: item.score, reverse=True)
        return {"results": ranked[: self.top_k]}

    def _reciprocal_rank_fusion(
        self, results: dict[str, list[SearchResult]]
    ) -> dict[str, SearchResult]:
        fused: dict[str, SearchResult] = {}
        for source, entries in results.items():
            for rank, entry in enumerate(entries, start=1):
                score = 1 / (self.rrf_k + rank)
                fused.setdefault(
                    entry.id,
                    SearchResult(
                        id=entry.id,
                        score=0.0,
                        text=entry.text,
                        metadata=entry.metadata,
                        source="hybrid",
                        sources=[source],
                    ),
                )
                fused_entry = fused[entry.id]
                fused_entry.score += score
                if source not in fused_entry.sources:
                    fused_entry.sources.append(source)
        return fused

    def _weighted_sum_fusion(
        self, results: dict[str, list[SearchResult]]
    ) -> dict[str, SearchResult]:
        fused: dict[str, SearchResult] = {}
        for source, entries in results.items():
            weight = self.weights.get(source, 1.0)
            for entry in entries:
                fused.setdefault(
                    entry.id,
                    SearchResult(
                        id=entry.id,
                        score=0.0,
                        text=entry.text,
                        metadata=entry.metadata,
                        source="hybrid",
                        sources=[source],
                    ),
                )
                fused_entry = fused[entry.id]
                fused_entry.score += weight * entry.score
                if source not in fused_entry.sources:
                    fused_entry.sources.append(source)
        return fused
