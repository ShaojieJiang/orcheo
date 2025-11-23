"""Query processing nodes for conversational search pipelines."""

from __future__ import annotations
import re
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.registry import NodeMetadata, registry


PRONOUN_PATTERN = re.compile(
    r"\b(it|this|that|they|them|those|these|he|she)\b", re.IGNORECASE
)


def _coerce_history_entries(history: list[Any]) -> list[str]:
    """Return normalized text entries extracted from conversation history."""
    normalized: list[str] = []
    for entry in history:
        if isinstance(entry, str):
            candidate = entry.strip()
        elif isinstance(entry, dict):
            candidate = str(entry.get("content", "")).strip()
        else:
            candidate = ""

        if candidate:
            normalized.append(candidate)
    return normalized


def _derive_referent(history_entries: list[str]) -> str | None:
    """Attempt to derive a referent phrase from the most recent history entry."""
    if not history_entries:
        return None

    most_recent = history_entries[0]
    match = re.findall(r"([A-Z][a-z0-9]+(?: [A-Z][a-z0-9]+)*)", most_recent)
    if match:
        referent = match[-1]
        referent = re.sub(r"^(The|A|An)\s+", "", referent).strip()
        if referent and referent.lower() not in {"the", "a", "an"}:
            return referent
        referent = ""

    tokens = [
        token
        for token in most_recent.split()
        if token and token.lower() not in {"the", "a", "an"}
    ]
    if tokens:
        return tokens[-1]
    return None


@registry.register(
    NodeMetadata(
        name="QueryRewriteNode",
        description=(
            "Rewrite or expand a user query using recent conversation history to"
            " improve retrieval recall."
        ),
        category="conversational_search",
    )
)
class QueryRewriteNode(TaskNode):
    """Node that rewrites a query using conversation snippets."""

    query_key: str = Field(
        default="query",
        description="Key inside ``state.inputs`` containing the user query.",
    )
    history_key: str = Field(
        default="history",
        description="Key inside ``state.inputs`` containing conversation history.",
    )
    max_history_messages: int = Field(
        default=3, gt=0, description="Maximum number of history turns to consider."
    )
    joiner: str = Field(
        default=" ",
        description="Separator used when appending contextual snippets to the query.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return a rewritten query that incorporates recent history."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "QueryRewriteNode requires a non-empty query string"
            raise ValueError(msg)

        raw_history = state.get("inputs", {}).get(self.history_key, [])
        if raw_history and not isinstance(raw_history, list):
            msg = "history payload must be a list when provided"
            raise ValueError(msg)

        normalized_history = _coerce_history_entries(raw_history)[
            : self.max_history_messages
        ]
        rewritten = query.strip()

        if normalized_history and PRONOUN_PATTERN.search(rewritten):
            context = self.joiner.join(normalized_history)
            rewritten = f"{rewritten} ({context})"
        elif normalized_history:
            context = normalized_history[0]
            rewritten = f"{rewritten} — context: {context}"

        return {"rewritten_query": rewritten, "history_used": normalized_history}


@registry.register(
    NodeMetadata(
        name="CoreferenceResolverNode",
        description="Resolve pronouns using recent conversation context.",
        category="conversational_search",
    )
)
class CoreferenceResolverNode(TaskNode):
    """Node that replaces ambiguous pronouns with derived referents."""

    query_key: str = Field(
        default="query",
        description="Key inside ``state.inputs`` containing the user query.",
    )
    history_key: str = Field(
        default="history",
        description="Key inside ``state.inputs`` containing conversation history.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Replace detected pronouns with a best-effort referent."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "CoreferenceResolverNode requires a non-empty query string"
            raise ValueError(msg)

        raw_history = state.get("inputs", {}).get(self.history_key, [])
        if raw_history and not isinstance(raw_history, list):
            msg = "history payload must be a list when provided"
            raise ValueError(msg)

        normalized_history = _coerce_history_entries(raw_history)
        referent = _derive_referent(normalized_history)

        resolved_query = query.strip()
        if referent and PRONOUN_PATTERN.search(resolved_query):
            resolved_query = PRONOUN_PATTERN.sub(referent, resolved_query)

        return {
            "resolved_query": resolved_query,
            "referent": referent,
            "history_used": normalized_history[:3],
        }


@registry.register(
    NodeMetadata(
        name="QueryClassifierNode",
        description="Classify the user's intent to control downstream routing.",
        category="conversational_search",
    )
)
class QueryClassifierNode(TaskNode):
    """Heuristic query classifier for conversational routing."""

    query_key: str = Field(
        default="query",
        description="Key inside ``state.inputs`` containing the user query.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return an intent label and confidence score."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "QueryClassifierNode requires a non-empty query string"
            raise ValueError(msg)

        normalized = query.strip().lower()
        intent = "search"
        confidence = 0.55

        if any(
            phrase in normalized
            for phrase in ["thanks", "that is all", "that's all", "goodbye", "bye"]
        ):
            intent = "finalization"
            confidence = 0.9
        elif any(
            keyword in normalized
            for keyword in [
                "clarify",
                "mean",
                "which one",
                "more detail",
                "what do you mean",
            ]
        ):
            intent = "clarification"
            confidence = 0.72
        elif normalized.endswith("?") or any(
            normalized.startswith(prefix)
            for prefix in ["what", "how", "why", "where", "who", "when"]
        ):
            intent = "search"
            confidence = 0.78

        return {"intent": intent, "confidence": confidence}


@registry.register(
    NodeMetadata(
        name="ContextCompressorNode",
        description="Deduplicate and trim retrieved context within a token budget.",
        category="conversational_search",
    )
)
class ContextCompressorNode(TaskNode):
    """Node that compresses retrieval results into a token-limited set."""

    source_result_key: str = Field(
        default="retrieval_results",
        description="Key inside ``state.results`` containing retrieval outputs.",
    )
    results_field: str = Field(
        default="results",
        description="Field name containing the list of SearchResult entries.",
    )
    max_tokens: int = Field(
        default=400,
        gt=0,
        description="Maximum approximate token budget for returned results.",
    )
    deduplicate: bool = Field(
        default=True, description="Whether to drop results with duplicate text."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return a compressed list of :class:`SearchResult` entries."""
        results = self._resolve_results(state)
        if not results:
            msg = "ContextCompressorNode requires at least one SearchResult"
            raise ValueError(msg)

        sorted_results = sorted(results, key=lambda entry: entry.score, reverse=True)
        compressed: list[SearchResult] = []
        seen_texts: set[str] = set()
        token_count = 0

        for entry in sorted_results:
            if self.deduplicate:
                fingerprint = entry.text.strip().lower()
                if fingerprint in seen_texts:
                    continue
                seen_texts.add(fingerprint)

            entry_tokens = len(entry.text.split())
            if token_count + entry_tokens > self.max_tokens:
                break

            compressed.append(entry)
            token_count += entry_tokens

        return {
            "results": compressed,
            "dropped": len(sorted_results) - len(compressed),
            "token_count": token_count,
        }

    def _resolve_results(self, state: State) -> list[SearchResult]:
        results = state.get("results", {}).get(self.source_result_key)
        if isinstance(results, dict) and self.results_field in results:
            payload = results[self.results_field]
        else:
            payload = results

        if payload is None:
            return []
        if not isinstance(payload, list):
            msg = "retrieval results must be provided as a list"
            raise ValueError(msg)

        return [SearchResult.model_validate(item) for item in payload]
