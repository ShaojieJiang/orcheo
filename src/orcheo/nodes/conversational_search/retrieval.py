"""Retrieval and fusion nodes for conversational search."""

from __future__ import annotations
import inspect
import math
import re
from collections import Counter
from collections.abc import Callable
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
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


EmbeddingFunction = Callable[[list[str]], list[list[float]]]


class _BM25Document(BaseModel):
    """Lightweight normalized document for BM25 scoring."""

    id: str
    content: str
    metadata: dict[str, Any]

    model_config = ConfigDict(extra="forbid")


@registry.register(
    NodeMetadata(
        name="VectorSearchNode",
        description="Perform dense similarity search using a vector store.",
        category="conversational_search",
    )
)
class VectorSearchNode(TaskNode):
    """Node that runs dense similarity search against a vector store."""

    query_key: str = Field(
        default="query",
        description="Key within ``state.inputs`` containing the query",
    )
    vector_store: BaseVectorStore = Field(
        default_factory=InMemoryVectorStore,
        description="Vector store adapter used for retrieval",
    )
    embedding_function: EmbeddingFunction | None = Field(
        default=None,
        description="Callable that embeds the user query for similarity search",
    )
    top_k: int = Field(default=10, gt=0, description="Number of hits to return")
    score_threshold: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum score required for a hit to be kept",
    )
    filter_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata filters passed to the store",
    )
    include_metadata: bool = Field(
        default=True,
        description="Whether to return metadata stored with the vector record",
    )
    result_source_name: str = Field(
        default="vector",
        description="Label applied to results from this node",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Embed the query and search the configured vector store."""
        query = self._resolve_query(state)
        query_vector = await self._embed([query])
        if len(query_vector) != 1:
            msg = "Embedding function must return exactly one vector for the query"
            raise ValueError(msg)

        raw_results = await self.vector_store.search(
            query_vector=query_vector[0],
            top_k=self.top_k,
            filter_metadata=self.filter_metadata or None,
            include_metadata=self.include_metadata,
        )

        results = [
            self._apply_source(SearchResult.model_validate(result))
            for result in raw_results
            if result.score >= self.score_threshold
        ]
        return {"results": results}

    def _resolve_query(self, state: State) -> str:
        query = state.get("inputs", {}).get(self.query_key)
        if query is None:
            msg = f"Missing query under inputs['{self.query_key}']"
            raise ValueError(msg)
        if not isinstance(query, str):
            msg = "query input must be a string"
            raise ValueError(msg)
        normalized = query.strip()
        if not normalized:
            msg = "query input cannot be empty"
            raise ValueError(msg)
        return normalized

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        embedder = self.embedding_function or self._default_embedding_function
        result = embedder(texts)
        if inspect.isawaitable(result):
            result = await result  # type: ignore[assignment]
        if not isinstance(result, list) or not all(
            isinstance(row, list) for row in result
        ):
            msg = "Embedding function must return List[List[float]]"
            raise ValueError(msg)
        return result

    @staticmethod
    def _default_embedding_function(texts: list[str]) -> list[list[float]]:
        """Deterministic embedding based on input length."""
        embeddings: list[list[float]] = []
        for text in texts:
            # Use length-derived embedding for reproducibility and tests
            embeddings.append([float(len(text))])
        return embeddings

    def _apply_source(self, result: SearchResult) -> SearchResult:
        sources = result.sources or []
        if not sources and self.result_source_name:
            sources = [self.result_source_name]
        update: dict[str, Any] = {"sources": sources}
        if result.source is None:
            update["source"] = self.result_source_name
        return result.model_copy(update=update)


@registry.register(
    NodeMetadata(
        name="BM25SearchNode",
        description="Perform sparse BM25 retrieval over in-memory documents.",
        category="conversational_search",
    )
)
class BM25SearchNode(TaskNode):
    """Lightweight BM25 retrieval that operates on provided documents."""

    query_key: str = Field(default="query", description="State input key for the query")
    source_result_key: str | None = Field(
        default=None,
        description="Optional result key containing documents to search",
    )
    documents_field: str = Field(
        default="documents",
        description="Field within the source result containing documents",
    )
    documents: list[Document | DocumentChunk | dict[str, Any] | str] = Field(
        default_factory=list,
        description="Inline corpus to search when state does not provide one",
    )
    top_k: int = Field(default=10, gt=0, description="Number of hits to return")
    score_threshold: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum score required for a hit to be included",
    )
    include_metadata: bool = Field(
        default=True,
        description="Whether to emit metadata with each hit",
    )
    k1: float = Field(default=1.5, gt=0, description="BM25 term frequency scaling")
    b: float = Field(default=0.75, ge=0.0, le=1.0, description="BM25 length norm")
    result_source_name: str = Field(
        default="bm25",
        description="Label applied to BM25 results",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Score documents using BM25 and return ranked results."""
        query = self._resolve_query(state)
        corpus = self._resolve_corpus(state)
        if not corpus:
            msg = "BM25SearchNode requires at least one document"
            raise ValueError(msg)

        query_tokens = self._tokenize(query)
        if not query_tokens:
            msg = "Query must contain at least one alphanumeric token"
            raise ValueError(msg)

        doc_tokens = [self._tokenize(doc.content) for doc in corpus]
        avgdl = sum(len(tokens) for tokens in doc_tokens) / len(doc_tokens)
        idf = self._inverse_document_frequency(doc_tokens)

        scored: list[SearchResult] = []
        for doc, tokens in zip(corpus, doc_tokens, strict=True):
            score = self._bm25_score(tokens, query_tokens, idf, avgdl)
            if score < self.score_threshold:
                continue
            metadata = doc.metadata if self.include_metadata else {}
            scored.append(
                SearchResult(
                    id=doc.id,
                    content=doc.content,
                    score=max(score, 0.0),
                    metadata=metadata,
                    source=self.result_source_name,
                    sources=[self.result_source_name],
                )
            )

        ranked = sorted(scored, key=lambda result: result.score, reverse=True)[
            : self.top_k
        ]
        return {"results": ranked}

    def _resolve_query(self, state: State) -> str:
        query = state.get("inputs", {}).get(self.query_key)
        if query is None:
            msg = f"Missing query under inputs['{self.query_key}']"
            raise ValueError(msg)
        if not isinstance(query, str):
            msg = "query input must be a string"
            raise ValueError(msg)
        normalized = query.strip()
        if not normalized:
            msg = "query input cannot be empty"
            raise ValueError(msg)
        return normalized

    def _resolve_corpus(self, state: State) -> list[_BM25Document]:
        documents: list[Any] = list(self.documents)
        if self.source_result_key:
            source = state.get("results", {}).get(self.source_result_key, {})
            if isinstance(source, dict) and self.documents_field in source:
                documents.extend(source[self.documents_field])
            elif source:
                documents.extend(source if isinstance(source, list) else [])

        normalized: list[_BM25Document] = []
        for document in documents:
            if isinstance(document, _BM25Document):
                normalized.append(document)
            elif isinstance(document, Document | DocumentChunk):
                normalized.append(
                    _BM25Document(
                        id=document.id,
                        content=document.content,
                        metadata=document.metadata,
                    )
                )
            elif isinstance(document, str):
                normalized.append(
                    _BM25Document(id=document, content=document, metadata={}),
                )
            elif isinstance(document, dict):
                normalized.append(_BM25Document(**document))
            else:
                msg = f"Unsupported document type: {type(document).__name__}"
                raise TypeError(msg)
        return normalized

    def _inverse_document_frequency(
        self, doc_tokens: list[list[str]]
    ) -> dict[str, float]:
        df: Counter[str] = Counter()
        for tokens in doc_tokens:
            df.update(set(tokens))
        num_docs = len(doc_tokens)
        return {
            term: math.log((num_docs - freq + 0.5) / (freq + 0.5) + 1)
            for term, freq in df.items()
        }

    def _bm25_score(
        self,
        tokens: list[str],
        query_tokens: list[str],
        idf: dict[str, float],
        avgdl: float,
    ) -> float:
        if not tokens:
            return 0.0
        term_freq = Counter(tokens)
        score = 0.0
        doc_len = len(tokens)
        for term in query_tokens:
            if term not in term_freq:
                continue
            freq = term_freq[term]
            numerator = idf.get(term, 0.0) * freq * (self.k1 + 1)
            denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / avgdl)
            score += numerator / denominator
        return score

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"\w+", text.lower())


@registry.register(
    NodeMetadata(
        name="HybridFusionNode",
        description="Fuse retrieval results using RRF or weighted strategies.",
        category="conversational_search",
    )
)
class HybridFusionNode(TaskNode):
    """Combine results from multiple retrievers using scoring fusion."""

    retrieval_results_key: str | None = Field(
        default=None,
        description="Optional key containing a mapping of retriever -> results",
    )
    source_result_keys: dict[str, str] = Field(
        default_factory=lambda: {"vector": "vector_search", "bm25": "bm25_search"},
        description="Mapping of retriever label to state results key",
    )
    strategy: str = Field(
        default="rrf",
        description="Fusion strategy: 'rrf' or 'weighted_sum'",
    )
    rrf_k: int = Field(
        default=60,
        gt=0,
        description="RRF hyperparameter controlling rank damping",
    )
    weights: dict[str, float] = Field(
        default_factory=dict,
        description="Weights applied per retriever for weighted_sum",
    )
    top_k: int = Field(default=10, gt=0, description="Number of fused hits to return")
    include_metadata: bool = Field(
        default=True,
        description="Whether to keep metadata on fused results",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Fuse retrieval results from configured retrievers."""
        sources = self._collect_sources(state)
        if not sources:
            msg = "HybridFusionNode requires at least one set of retrieval results"
            raise ValueError(msg)

        fused_scores: dict[str, float] = {}
        fused_payloads: dict[str, SearchResult] = {}

        for label, results in sources.items():
            normalized = [self._normalize_result(result, label) for result in results]
            for rank, result in enumerate(normalized, start=1):
                contribution = self._score_contribution(label, result, rank)
                fused_scores[result.id] = (
                    fused_scores.get(result.id, 0.0) + contribution
                )

                payload = fused_payloads.get(result.id)
                if payload is None:
                    payload = result
                else:
                    merged_sources = list(
                        dict.fromkeys(payload.sources + result.sources)
                    )
                    payload = payload.model_copy(update={"sources": merged_sources})
                fused_payloads[result.id] = payload

        fused_results = [
            result.model_copy(update={"score": fused_scores[result_id]})
            for result_id, result in fused_payloads.items()
        ]
        ranked = sorted(fused_results, key=lambda res: res.score, reverse=True)[
            : self.top_k
        ]
        return {"results": ranked}

    def _collect_sources(self, state: State) -> dict[str, list[Any]]:
        sources: dict[str, list[Any]] = {}
        container = None
        if self.retrieval_results_key:
            container = state.get("results", {}).get(self.retrieval_results_key)
            if container is None:
                container = state.get("inputs", {}).get(self.retrieval_results_key)
        if isinstance(container, dict):
            for label, payload in container.items():
                sources[label] = self._extract_results(payload)

        for label, key in self.source_result_keys.items():
            payload = state.get("results", {}).get(key)
            if payload is None or label in sources:
                continue
            sources[label] = self._extract_results(payload)
        return sources

    def _extract_results(self, payload: Any) -> list[Any]:
        if isinstance(payload, dict) and "results" in payload:
            payload = payload["results"]
        if not isinstance(payload, list):
            msg = "retrieval results must be a list"
            raise ValueError(msg)
        return payload

    def _normalize_result(self, result: Any, label: str) -> SearchResult:
        model = SearchResult.model_validate(result)
        metadata = model.metadata if self.include_metadata else {}
        sources = model.sources or []
        if label not in sources:
            sources.append(label)
        update = {
            "source": model.source or label,
            "metadata": metadata,
            "sources": sources,
        }
        return model.model_copy(update=update)

    def _score_contribution(self, label: str, result: SearchResult, rank: int) -> float:
        if self.strategy == "weighted_sum":
            weight = self.weights.get(label, 1.0)
            return result.score * weight
        if self.strategy != "rrf":
            msg = "Fusion strategy must be either 'rrf' or 'weighted_sum'"
            raise ValueError(msg)
        return 1.0 / (self.rrf_k + rank)
