"""Query processing nodes for conversational search flows."""

from __future__ import annotations
import re
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="QueryRewriteNode",
        description="Rewrite user queries using recent conversation context.",
        category="conversational_search",
    )
)
class QueryRewriteNode(TaskNode):
    """Expand or clarify the user query with recent conversation history."""

    query_key: str = Field(
        default="query",
        description="Key within ``state.inputs`` containing the raw query.",
    )
    conversation_key: str = Field(
        default="conversation_history",
        description="Key within ``state.inputs`` holding prior conversation turns.",
    )
    history_window: int = Field(
        default=3, ge=1, description="Number of most recent turns to include."
    )
    separator: str = Field(
        default=" ", description="Separator used when joining context snippets."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Rewrite the query by appending a compact conversation summary."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "QueryRewriteNode requires a non-empty query string"
            raise ValueError(msg)

        history = self._resolve_history(state)
        rewritten = query.strip()
        if history:
            context = self.separator.join(history[-self.history_window :])
            rewritten = f"{rewritten} (context: {context})"

        return {"rewritten_query": rewritten, "original_query": query.strip()}

    def _resolve_history(self, state: State) -> list[str]:
        raw_history = state.get("inputs", {}).get(self.conversation_key)
        if raw_history is None:
            return []
        if not isinstance(raw_history, list):
            msg = "conversation_history must be a list when provided"
            raise ValueError(msg)

        history: list[str] = []
        for item in raw_history:
            if isinstance(item, str):
                content = item
            elif isinstance(item, dict) and isinstance(item.get("content"), str):
                content = item["content"]
            else:
                msg = (
                    "conversation_history entries must be strings or mappings with "
                    "'content'"
                )
                raise ValueError(msg)
            cleaned = content.strip()
            if cleaned:
                history.append(cleaned)
        return history


@registry.register(
    NodeMetadata(
        name="CoreferenceResolverNode",
        description="Resolve pronouns in the query using recent context.",
        category="conversational_search",
    )
)
class CoreferenceResolverNode(TaskNode):
    """Replace ambiguous pronouns using a simple conversation-aware heuristic."""

    query_key: str = Field(
        default="query",
        description="Key within ``state.inputs`` containing the raw query.",
    )
    conversation_key: str = Field(
        default="conversation_history",
        description="Key within ``state.inputs`` holding prior conversation turns.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Resolve pronouns based on the last available conversation mention."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "CoreferenceResolverNode requires a non-empty query string"
            raise ValueError(msg)

        history = state.get("inputs", {}).get(self.conversation_key) or []
        antecedent = self._extract_antecedent(history)
        resolved_query = query.strip()
        if antecedent:
            resolved_query = self._replace_pronouns(resolved_query, antecedent)

        return {"resolved_query": resolved_query, "antecedent": antecedent}

    def _extract_antecedent(self, history: Any) -> str | None:
        if not isinstance(history, list) or not history:
            return None
        last_entry = history[-1]
        if isinstance(last_entry, str):
            candidate = last_entry.strip()
        elif isinstance(last_entry, dict):
            candidate = str(last_entry.get("content", "")).strip()
        else:
            return None
        return candidate or None

    def _replace_pronouns(self, query: str, antecedent: str) -> str:
        pronouns = re.compile(r"\b(it|this|that|they|them)\b", flags=re.IGNORECASE)
        return pronouns.sub(antecedent, query)


@registry.register(
    NodeMetadata(
        name="QueryClassifierNode",
        description="Classify the query intent for routing.",
        category="conversational_search",
    )
)
class QueryClassifierNode(TaskNode):
    """Heuristic query intent classifier supporting search workflows."""

    query_key: str = Field(
        default="query",
        description="Key within ``state.inputs`` containing the raw query.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return a coarse intent label to drive graph routing."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "QueryClassifierNode requires a non-empty query string"
            raise ValueError(msg)

        intent = self._classify(query.strip())
        return {"intent": intent}

    def _classify(self, query: str) -> str:
        normalized = query.lower().strip()
        if any(phrase in normalized for phrase in ("thank", "thanks", "appreciate")):
            return "finalize"
        clarification_triggers = (
            "clarify",
            "mean",
            "can you explain",
            "not sure",
            "what do you mean",
        )
        if any(trigger in normalized for trigger in clarification_triggers):
            return "clarification"
        if normalized.endswith("?") or any(
            keyword in normalized
            for keyword in ("how", "what", "why", "where", "search")
        ):
            return "search"
        return "chat"


@registry.register(
    NodeMetadata(
        name="ContextCompressorNode",
        description="Deduplicate and trim retrieved context within a token budget.",
        category="conversational_search",
    )
)
class ContextCompressorNode(TaskNode):
    """Prepare retrieval results for generation by enforcing a token budget."""

    source_results_key: str = Field(
        default="retrieval_results",
        description="Key within ``state.results`` containing retriever outputs.",
    )
    max_tokens: int = Field(
        default=800, gt=0, description="Maximum approximate tokens to retain."
    )
    deduplicate: bool = Field(
        default=True, description="Whether to merge duplicate result texts."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return compressed retrieval results within the configured budget."""
        results = self._resolve_results(state)
        if not results:
            msg = "ContextCompressorNode requires at least one retrieval result"
            raise ValueError(msg)

        compressed: list[SearchResult] = []
        seen: dict[str, int] = {}
        token_count = 0

        for result in results:
            tokens = self._estimate_tokens(result.text)
            if token_count + tokens > self.max_tokens:
                break

            normalized = result.text.strip().lower()
            if self.deduplicate and normalized in seen:
                existing = compressed[seen[normalized]]
                merged_sources = sorted(set(existing.sources + result.sources))
                existing.sources = merged_sources
                existing.source = existing.source or result.source
                if result.score > existing.score:
                    existing.score = result.score
                    existing.metadata = result.metadata
                continue

            compressed.append(result.model_copy(deep=True))
            seen[normalized] = len(compressed) - 1
            token_count += tokens

        dropped = max(0, len(results) - len(compressed))
        return {"compressed_results": compressed, "dropped_results": dropped}

    def _resolve_results(self, state: State) -> list[SearchResult]:
        results = state.get("results", {})
        payload = results.get(self.source_results_key)
        if payload is None:
            return []
        collected: list[Any]
        if isinstance(payload, dict):
            collected = []
            for value in payload.values():
                if not isinstance(value, list):
                    msg = "retrieval_results entries must be lists of SearchResult"
                    raise ValueError(msg)
                collected.extend(value)
        elif isinstance(payload, list):
            collected = payload
        else:
            msg = "retrieval_results must be a mapping or list"
            raise ValueError(msg)

        return [SearchResult.model_validate(item) for item in collected]

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text.split()))
