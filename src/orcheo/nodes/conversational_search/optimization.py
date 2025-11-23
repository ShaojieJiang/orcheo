"""Optimization and operations nodes for conversational search."""

from __future__ import annotations
import time
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="AnswerCachingNode",
        description="Cache question/answer pairs to reduce latency on repeats.",
        category="conversational_search",
    )
)
class AnswerCachingNode(TaskNode):
    """In-memory cache for repeated queries."""

    query_key: str = Field(
        default="query", description="Key within inputs holding the user query"
    )
    response_result_key: str = Field(
        default="grounded_generator",
        description="Upstream result entry containing the latest response.",
    )
    response_field: str = Field(
        default="response", description="Field carrying the generated text"
    )
    max_cache_size: int = Field(
        default=128,
        gt=0,
        description="Maximum number of cached entries before eviction",
    )

    cache: dict[str, dict[str, Any]] = Field(default_factory=dict)
    cache_order: list[str] = Field(default_factory=list)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return cached answers or store new entries from upstream."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "AnswerCachingNode requires a non-empty query string"
            raise ValueError(msg)
        normalized_query = query.strip()

        if normalized_query in self.cache:
            entry = self.cache[normalized_query]
            return {
                "cached": True,
                "response": entry["response"],
                "metadata": entry["metadata"],
            }

        payload = state.get("results", {}).get(self.response_result_key, {})
        if not isinstance(payload, dict):
            msg = "Response payload must be a mapping"
            raise ValueError(msg)
        response = payload.get(self.response_field)
        if not isinstance(response, str) or not response.strip():
            msg = "Response must be a non-empty string to cache"
            raise ValueError(msg)
        metadata = {"citations": payload.get("citations", [])}

        self._evict_if_needed()
        self.cache[normalized_query] = {
            "response": response.strip(),
            "metadata": metadata,
        }
        self.cache_order.append(normalized_query)
        return {"cached": False, "response": response.strip(), "metadata": metadata}

    def _evict_if_needed(self) -> None:
        while len(self.cache_order) >= self.max_cache_size:
            oldest = self.cache_order.pop(0)
            self.cache.pop(oldest, None)


@registry.register(
    NodeMetadata(
        name="SessionManagementNode",
        description="Track active sessions and enforce concurrency limits.",
        category="conversational_search",
    )
)
class SessionManagementNode(TaskNode):
    """Maintain session lifecycle constraints for conversational flows."""

    session_key: str = Field(
        default="session_id",
        description="Key within inputs identifying the current session",
    )
    max_sessions: int = Field(
        default=100,
        gt=0,
        description="Maximum concurrently tracked sessions before eviction",
    )
    max_requests_per_session: int = Field(
        default=0,
        ge=0,
        description="Optional cap on requests per session (0 disables limit)",
    )

    sessions: dict[str, int] = Field(default_factory=dict)
    session_order: list[tuple[float, str]] = Field(default_factory=list)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Register the session and indicate whether processing is allowed."""
        session_id = state.get("inputs", {}).get(self.session_key)
        if not isinstance(session_id, str) or not session_id.strip():
            msg = "SessionManagementNode requires a non-empty session identifier"
            raise ValueError(msg)
        normalized = session_id.strip()

        evicted = self._evict_if_needed(normalized)
        count = self.sessions.get(normalized, 0) + 1
        self.sessions[normalized] = count
        self.session_order.append((time.monotonic(), normalized))

        allowed = True
        if self.max_requests_per_session and count > self.max_requests_per_session:
            allowed = False

        return {
            "session_id": normalized,
            "allowed": allowed,
            "request_count": count,
            "evicted": evicted,
            "active_sessions": len(self.sessions),
        }

    def _evict_if_needed(self, current_session: str) -> list[str]:
        evicted: list[str] = []
        while len(self.sessions) >= self.max_sessions and self.session_order:
            _, oldest = self.session_order.pop(0)
            if oldest == current_session:
                continue
            self.sessions.pop(oldest, None)
            evicted.append(oldest)
        return evicted


@registry.register(
    NodeMetadata(
        name="MultiHopPlannerNode",
        description="Draft a simple multi-hop retrieval plan from the query text.",
        category="conversational_search",
    )
)
class MultiHopPlannerNode(TaskNode):
    """Generate a lightweight plan for multi-hop questions."""

    query_key: str = Field(
        default="query", description="Key within inputs holding the user query"
    )
    max_hops: int = Field(
        default=3, gt=0, description="Upper bound on hops included in the plan"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Split the query into ordered hops for downstream execution."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "MultiHopPlannerNode requires a non-empty query string"
            raise ValueError(msg)
        segments = [
            segment.strip() for segment in query.replace("?", ".").split(" and ")
        ]
        hops = [segment for segment in segments if segment]
        if not hops:
            hops = [query.strip()]
        hops = hops[: self.max_hops]
        return {"plan": hops, "hop_count": len(hops), "strategy": "sequential"}
