"""Guardrail and routing nodes for conversational search."""

from __future__ import annotations
from collections.abc import Callable
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.generation import _truncate_snippet
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.registry import NodeMetadata, registry


HallucinationDetector = Callable[[str, list[dict[str, Any]]], bool]
ReRankScorer = Callable[[SearchResult], float]


@registry.register(
    NodeMetadata(
        name="HallucinationGuardNode",
        description="Validate responses for grounding and route on hallucination.",
        category="conversational_search",
    )
)
class HallucinationGuardNode(TaskNode):
    """Detect hallucinations using citation presence heuristics or custom logic."""

    response_result_key: str = Field(
        default="grounded_generator",
        description="Upstream result entry containing generator output.",
    )
    response_field: str = Field(
        default="response", description="Field with generated text"
    )
    citations_field: str = Field(
        default="citations", description="Field carrying citation payloads"
    )
    fallback_route: str = Field(
        default="regenerate", description="Route returned when hallucination found"
    )
    detector: HallucinationDetector | None = Field(
        default=None,
        description="Optional callable returning True when the response is grounded.",
    )
    allow_empty_citations: bool = Field(
        default=False,
        description="Permit responses without citations when no context is supplied.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Validate the response and emit routing metadata."""
        payload = state.get("results", {}).get(self.response_result_key, {})
        if not isinstance(payload, dict):
            msg = "HallucinationGuardNode requires a mapping payload"
            raise ValueError(msg)

        response = payload.get(self.response_field)
        citations = payload.get(self.citations_field, [])
        if not isinstance(response, str) or not response.strip():
            msg = "Response must be a non-empty string"
            raise ValueError(msg)
        if not isinstance(citations, list):
            msg = "Citations payload must be a list"
            raise ValueError(msg)

        grounded = self._detect_grounding(response, citations)
        status = "pass" if grounded else "flagged"
        route = "proceed" if grounded else self.fallback_route
        reason = None if grounded else "Response missing required citations"
        return {
            "status": status,
            "route": route,
            "reason": reason,
            "response": response.strip(),
            "citations": citations,
        }

    def _detect_grounding(self, response: str, citations: list[dict[str, Any]]) -> bool:
        if self.detector is not None:
            return bool(self.detector(response, citations))
        if not citations:
            return self.allow_empty_citations
        missing = [
            citation
            for citation in citations
            if str(citation.get("id")) not in response
        ]
        return not missing


@registry.register(
    NodeMetadata(
        name="ReRankerNode",
        description="Re-rank retrieval results using a scoring function.",
        category="conversational_search",
    )
)
class ReRankerNode(TaskNode):
    """Apply a reranking function over search results."""

    results_field: str = Field(
        default="results", description="Key holding retrieval results to rerank"
    )
    top_k: int = Field(default=10, gt=0, description="Maximum results to return")
    scorer: ReRankScorer | None = Field(
        default=None,
        description="Optional callable that assigns a rerank score to SearchResult",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Reorder results by scorer or original score."""
        results = state.get("results", {}).get(self.results_field)
        entries = self._normalize_results(results)
        scorer = self.scorer or (lambda result: result.score)
        ranked = sorted(entries, key=scorer, reverse=True)[: self.top_k]
        return {"results": ranked}

    def _normalize_results(self, payload: Any) -> list[SearchResult]:
        if payload is None:
            return []
        if isinstance(payload, dict) and "results" in payload:
            payload = payload["results"]
        if not isinstance(payload, list):
            msg = "ReRankerNode requires a list of results"
            raise ValueError(msg)
        return [SearchResult.model_validate(item) for item in payload]


@registry.register(
    NodeMetadata(
        name="SourceRouterNode",
        description="Route downstream nodes based on the leading result source.",
        category="conversational_search",
    )
)
class SourceRouterNode(TaskNode):
    """Choose a route based on the origin of the top retrieval result."""

    results_field: str = Field(
        default="results", description="Key holding retrieval or reranked results"
    )
    routing_table: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of source name to downstream route identifier",
    )
    default_route: str = Field(
        default="vector", description="Fallback route when no mapping matches"
    )
    empty_route: str = Field(
        default="fallback", description="Route returned when no results are present"
    )
    prefer_sorted_order: bool = Field(
        default=True,
        description=(
            "When True, respect existing ordering of results instead of re-sorting by"
            " score when choosing a route."
        ),
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Select a route using the highest-scoring result."""
        payload = state.get("results")
        if isinstance(payload, dict) and self.results_field in payload:
            payload = payload[self.results_field]
        entries = self._normalize_results(payload)
        if not entries:
            return {"route": self.empty_route, "source": None}

        top = (
            entries[0]
            if self.prefer_sorted_order
            else max(entries, key=lambda item: item.score)
        )
        primary_source = (
            top.sources[0]
            if top.sources
            else top.source
            if top.source is not None
            else "unknown"
        )
        route = self.routing_table.get(primary_source, self.default_route)
        return {"route": route, "source": primary_source}

    def _normalize_results(self, payload: Any) -> list[SearchResult]:
        if payload is None:
            return []
        if isinstance(payload, dict) and "results" in payload:
            payload = payload["results"]
        if isinstance(payload, SearchResult):
            payload = [payload]
        if not isinstance(payload, list):
            msg = "SourceRouterNode requires a list of results"
            raise ValueError(msg)
        return [SearchResult.model_validate(item) for item in payload]


@registry.register(
    NodeMetadata(
        name="CitationsFormatterNode",
        description="Normalize citations for downstream display components.",
        category="conversational_search",
    )
)
class CitationsFormatterNode(TaskNode):
    """Produce structured citation entries from search results."""

    results_field: str = Field(
        default="results", description="Key holding retrieval results to format"
    )
    snippet_length: int = Field(
        default=160, gt=0, description="Maximum characters to include per snippet"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Format citations for UI consumption."""
        payload = state.get("results")
        if isinstance(payload, dict) and self.results_field in payload:
            payload = payload[self.results_field]
        entries = self._normalize_results(payload)
        citations = [
            self._format_entry(index, entry) for index, entry in enumerate(entries)
        ]
        return {"citations": citations}

    def _normalize_results(self, payload: Any) -> list[SearchResult]:
        if payload is None:
            return []
        if isinstance(payload, dict) and "results" in payload:
            payload = payload["results"]
        if isinstance(payload, SearchResult):
            payload = [payload]
        if not isinstance(payload, list):
            msg = "CitationsFormatterNode requires a list of results"
            raise ValueError(msg)
        return [SearchResult.model_validate(item) for item in payload]

    def _format_entry(self, index: int, entry: SearchResult) -> dict[str, Any]:
        metadata = entry.metadata or {}
        return {
            "id": str(index + 1),
            "title": metadata.get("title"),
            "url": metadata.get("url"),
            "snippet": _truncate_snippet(entry.text, self.snippet_length),
            "sources": entry.sources or ([entry.source] if entry.source else []),
        }
