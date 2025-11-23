"""Query processing nodes for conversational search workflows."""

from __future__ import annotations
import re
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.registry import NodeMetadata, registry


def _normalise_text(text: str) -> str:
    """Return a lowercased, whitespace-collapsed version of ``text``."""
    return " ".join(text.lower().split())


def _get_history_entries(state: State, key: str) -> list[Any]:
    """Return the raw history payload ensuring it is a list of supported entries."""
    payload = state.get("inputs", {}).get(key) or state.get("results", {}).get(key)
    if payload is None:
        return []
    if not isinstance(payload, list):
        msg = f"History payload for {key} must be a list"
        raise ValueError(msg)

    for entry in payload:
        if isinstance(entry, str):
            continue
        if (
            isinstance(entry, dict)
            and "content" in entry
            and isinstance(entry.get("content"), str)
        ):
            continue
        msg = "History entries must be strings or mappings with 'content'"
        raise ValueError(msg)
    return list(payload)


def _extract_history_text(entries: list[Any]) -> list[str]:
    """Return textual content from history entries."""
    texts: list[str] = []
    for entry in entries:
        if isinstance(entry, str):
            texts.append(entry)
        elif isinstance(entry, dict):
            content = entry.get("content")
            if isinstance(content, str):
                texts.append(content)
    return texts


@registry.register(
    NodeMetadata(
        name="QueryRewriteNode",
        description="Rewrite a query using conversation context to improve recall.",
        category="conversational_search",
    )
)
class QueryRewriteNode(TaskNode):
    """Node that expands or rewrites a query using recent conversation turns."""

    query_key: str = Field(
        default="query",
        description="Key within ``state.inputs`` containing the user query.",
    )
    history_key: str = Field(
        default="history",
        description="Key containing prior conversation turns for context.",
    )
    max_history_turns: int = Field(
        default=3, ge=0, description="Number of recent turns to include in rewrite"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Rewrite the incoming query with a short context summary."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "QueryRewriteNode requires a non-empty query string"
            raise ValueError(msg)

        history_entries = _get_history_entries(state, self.history_key)
        window = (
            history_entries[-self.max_history_turns :] if self.max_history_turns else []
        )

        if not window:
            return {
                "rewritten_query": query.strip(),
                "original_query": query.strip(),
                "context_window": [],
            }

        context = " ".join(
            turn.strip() for turn in _extract_history_text(window) if turn.strip()
        )
        rewritten = (
            f"{query.strip()} (context: {context})" if context else query.strip()
        )

        return {
            "rewritten_query": rewritten,
            "original_query": query.strip(),
            "context_window": window,
        }


@registry.register(
    NodeMetadata(
        name="CoreferenceResolverNode",
        description="Resolve pronouns/entities in the query using recent mentions.",
        category="conversational_search",
    )
)
class CoreferenceResolverNode(TaskNode):
    """Resolve ambiguous pronouns using provided entities or conversation history."""

    query_key: str = Field(
        default="query",
        description="Key within ``state.inputs`` containing the user query.",
    )
    history_key: str = Field(
        default="history",
        description="Key containing prior conversation turns for antecedent lookup.",
    )
    entities_key: str = Field(
        default="entities",
        description="Key with a list of candidate antecedents to substitute.",
    )
    pronouns: list[str] = Field(
        default_factory=lambda: [
            "it",
            "this",
            "that",
            "they",
            "them",
            "he",
            "she",
            "these",
            "those",
        ],
        description="Pronouns that will be replaced when antecedents are found.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Replace pronouns with the latest antecedent when available."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "CoreferenceResolverNode requires a non-empty query string"
            raise ValueError(msg)

        antecedent = self._resolve_antecedent(state)
        if antecedent is None:
            return {
                "resolved_query": query.strip(),
                "original_query": query.strip(),
                "antecedent": None,
            }

        pattern = re.compile(
            r"\b(" + "|".join(map(re.escape, self.pronouns)) + r")\b",
            re.IGNORECASE,
        )
        resolved_query = pattern.sub(antecedent, query)

        return {
            "resolved_query": resolved_query.strip(),
            "original_query": query.strip(),
            "antecedent": antecedent,
        }

    def _resolve_antecedent(self, state: State) -> str | None:
        entities = self._extract_entities(state)
        if entities:
            return entities[-1]

        history_entries = _get_history_entries(state, self.history_key)
        history = _extract_history_text(history_entries)
        for entry in reversed(history):
            if entry.strip():
                return entry.strip()
        return None

    def _extract_entities(self, state: State) -> list[str]:
        inputs = state.get("inputs", {})
        results = state.get("results", {})
        candidates: list[Any] = []

        if self.entities_key in inputs:
            candidates.append(inputs[self.entities_key])
        if isinstance(results, dict):
            for value in results.values():
                if isinstance(value, dict) and self.entities_key in value:
                    candidates.append(value[self.entities_key])

        entities: list[str] = []
        for candidate in candidates:
            if isinstance(candidate, list):
                entities.extend([item for item in candidate if isinstance(item, str)])
            elif isinstance(candidate, str):
                entities.append(candidate)
        return entities


@registry.register(
    NodeMetadata(
        name="QueryClassifierNode",
        description="Classify query intent to guide routing decisions.",
        category="conversational_search",
    )
)
class QueryClassifierNode(TaskNode):
    """Lightweight heuristic classifier for query intent."""

    query_key: str = Field(
        default="query",
        description="Key within ``state.inputs`` containing the user query.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return an intent label for the provided query."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "QueryClassifierNode requires a non-empty query string"
            raise ValueError(msg)

        label = self._classify(query)
        return {
            "intent": label,
            "is_search": label == "search",
            "original_query": query.strip(),
        }

    @staticmethod
    def _classify(query: str) -> str:
        text = query.strip().lower()
        if any(phrase in text for phrase in {"thank", "that's all", "no further"}):
            return "finalization"
        if "?" in text and len(text.split()) <= 4:
            return "clarification"
        if any(
            phrase in text for phrase in {"clarify", "which one", "what do you mean"}
        ):
            return "clarification"
        return "search"


@registry.register(
    NodeMetadata(
        name="ContextCompressorNode",
        description="Deduplicate and trim retrieved context to a token budget.",
        category="conversational_search",
    )
)
class ContextCompressorNode(TaskNode):
    """Compress retrieval results by deduplicating and enforcing a token budget."""

    source_result_key: str = Field(
        default="retrieval_results",
        description="Name of the upstream result containing retrieval outputs.",
    )
    results_field: str = Field(
        default="results",
        description="Field name holding the list of :class:`SearchResult` entries.",
    )
    token_budget: int = Field(
        default=200,
        gt=0,
        description="Maximum number of whitespace-delimited tokens to keep in context.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return deduplicated search results within the configured token budget."""
        entries = self._resolve_results(state)
        if not entries:
            msg = "ContextCompressorNode requires at least one result to compress"
            raise ValueError(msg)

        compressed: list[SearchResult] = []
        seen_texts: set[str] = set()
        dropped_ids: list[str] = []
        total_tokens = 0

        for entry in entries:
            normalised = _normalise_text(entry.text)
            if normalised in seen_texts:
                dropped_ids.append(entry.id)
                continue

            entry_tokens = len(entry.text.split())
            if total_tokens + entry_tokens > self.token_budget:
                break

            compressed.append(entry)
            seen_texts.add(normalised)
            total_tokens += entry_tokens

        return {
            "results": compressed,
            "dropped_ids": dropped_ids,
            "total_tokens": total_tokens,
        }

    def _resolve_results(self, state: State) -> list[SearchResult]:
        results = state.get("results", {}).get(self.source_result_key)
        if results is None:
            return []

        payload: Any
        if isinstance(results, dict) and self.results_field in results:
            payload = results[self.results_field]
        else:
            payload = results

        if not isinstance(payload, list):
            msg = "Retrieval results payload must be a list"
            raise ValueError(msg)

        return [SearchResult.model_validate(item) for item in payload]
