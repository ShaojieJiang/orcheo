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


def _normalize_messages(history: list[Any]) -> list[str]:
    messages: list[str] = []
    for entry in history:
        if isinstance(entry, str):
            content = entry
        elif isinstance(entry, dict):
            content = str(entry.get("content", "")).strip()
        else:
            continue
        if content:
            messages.append(content)
    return messages


@registry.register(
    NodeMetadata(
        name="QueryRewriteNode",
        description=(
            "Rewrite or expand a query using recent conversation context to"
            " improve recall."
        ),
        category="conversational_search",
    )
)
class QueryRewriteNode(TaskNode):
    """Rewrite queries using conversation history and simple heuristics."""

    query_key: str = Field(
        default="query", description="Key within ``state.inputs`` holding the query."
    )
    history_key: str = Field(
        default="history",
        description="Key within ``state.inputs`` containing conversation history.",
    )
    max_history_messages: int = Field(
        default=3, gt=0, description="Number of prior messages to consider."
    )

    pronouns: set[str] = Field(
        default_factory=lambda: {
            "it",
            "they",
            "them",
            "this",
            "that",
            "these",
            "those",
            "he",
            "she",
        },
        description="Pronouns that trigger contextual rewriting.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Rewrite queries using recent history when pronouns are detected."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "QueryRewriteNode requires a non-empty query string"
            raise ValueError(msg)

        history = state.get("inputs", {}).get(self.history_key, []) or []
        if not isinstance(history, list):
            msg = "history must be a list of messages"
            raise ValueError(msg)

        messages = _normalize_messages(history)[-self.max_history_messages :]
        context = " ".join(messages)
        needs_rewrite = self._contains_pronoun(query) and bool(context)

        rewritten = query.strip()
        if needs_rewrite:
            rewritten = f"{rewritten}. Context: {context}".strip()

        return {
            "original_query": query,
            "query": rewritten,
            "used_history": needs_rewrite,
            "context": context,
        }

    def _contains_pronoun(self, query: str) -> bool:
        tokens = re.findall(r"\b\w+\b", query.lower())
        return any(token in self.pronouns for token in tokens)


@registry.register(
    NodeMetadata(
        name="CoreferenceResolverNode",
        description="Resolve simple pronouns using prior conversation turns.",
        category="conversational_search",
    )
)
class CoreferenceResolverNode(TaskNode):
    """Resolve pronouns in queries using the latest referenced entity."""

    query_key: str = Field(
        default="query", description="Key within ``state.inputs`` holding the query."
    )
    history_key: str = Field(
        default="history",
        description="Key within ``state.inputs`` containing conversation history.",
    )
    pronouns: set[str] = Field(
        default_factory=lambda: {"it", "they", "this", "that", "those", "them"},
        description="Pronouns that should be resolved when context exists.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Replace pronouns in the query using a recent referent if available."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "CoreferenceResolverNode requires a non-empty query string"
            raise ValueError(msg)

        history = state.get("inputs", {}).get(self.history_key, []) or []
        if not isinstance(history, list):
            msg = "history must be a list of messages"
            raise ValueError(msg)

        referent = self._last_referent(history)
        resolved_query, resolved = self._resolve(query, referent)

        return {
            "query": resolved_query,
            "resolved": resolved,
            "antecedent": referent if resolved else None,
        }

    def _last_referent(self, history: list[Any]) -> str | None:
        messages = _normalize_messages(history)
        if not messages:
            return None
        return messages[-1]

    def _resolve(self, query: str, referent: str | None) -> tuple[str, bool]:
        if not referent:
            return query.strip(), False

        tokens = query.strip().split()
        resolved = False
        for index, token in enumerate(tokens):
            stripped = token.rstrip(".,?!").lower()
            if stripped in self.pronouns:
                suffix = token[len(stripped) :]
                tokens[index] = f"{referent}{suffix}"
                resolved = True
                break
        return " ".join(tokens), resolved


@registry.register(
    NodeMetadata(
        name="QueryClassifierNode",
        description="Classify a query intent to support routing decisions.",
        category="conversational_search",
    )
)
class QueryClassifierNode(TaskNode):
    """Heuristic classifier for determining query intent."""

    query_key: str = Field(
        default="query", description="Key within ``state.inputs`` holding the query."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Classify the query as search, clarification, or finalization."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "QueryClassifierNode requires a non-empty query string"
            raise ValueError(msg)

        normalized = query.strip().lower()
        classification = "search"
        confidence = 0.6

        if any(
            token in normalized for token in {"clarify", "more detail", "which one"}
        ):
            classification = "clarification"
            confidence = 0.8
        elif normalized.startswith(("thanks", "thank you", "that helps")):
            classification = "finalization"
            confidence = 0.9

        return {"classification": classification, "confidence": confidence}


@registry.register(
    NodeMetadata(
        name="ContextCompressorNode",
        description="Deduplicate and budget retrieval results for downstream nodes.",
        category="conversational_search",
    )
)
class ContextCompressorNode(TaskNode):
    """Deduplicate and trim retrieval results to a token budget."""

    results_field: str = Field(
        default="retrieval_results",
        description="Key in ``state.results`` that holds retrieval payloads.",
    )
    max_tokens: int = Field(
        default=800, gt=0, description="Maximum whitespace token budget for context."
    )
    deduplicate: bool = Field(
        default=True, description="Whether to drop duplicate result identifiers."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return a token-budgeted subset of retrieval results."""
        results_payload = state.get("results", {}).get(self.results_field)
        if results_payload is None:
            msg = "ContextCompressorNode requires retrieval results to compress"
            raise ValueError(msg)

        if isinstance(results_payload, dict) and "results" in results_payload:
            entries = results_payload["results"]
        else:
            entries = results_payload

        if not isinstance(entries, list):
            msg = "retrieval results must be provided as a list"
            raise ValueError(msg)

        results = [SearchResult.model_validate(item) for item in entries]
        sorted_results = sorted(results, key=lambda item: item.score, reverse=True)

        kept: list[SearchResult] = []
        seen_ids: set[str] = set()
        total_tokens = 0
        truncated = False

        for result in sorted_results:
            if self.deduplicate and result.id in seen_ids:
                continue

            tokens = self._token_count(result.text)
            if total_tokens + tokens > self.max_tokens:
                truncated = True
                break

            kept.append(result)
            total_tokens += tokens
            seen_ids.add(result.id)

        return {"results": kept, "total_tokens": total_tokens, "truncated": truncated}

    @staticmethod
    def _token_count(text: str) -> int:
        return len(text.split())


@registry.register(
    NodeMetadata(
        name="MultiHopPlannerNode",
        description="Derive sequential sub-queries for multi-hop answering.",
        category="conversational_search",
    )
)
class MultiHopPlannerNode(TaskNode):
    """Decompose complex queries into sequential hop plans."""

    query_key: str = Field(
        default="query", description="Key within inputs containing the question"
    )
    max_hops: int = Field(default=3, gt=0)
    delimiter: str = Field(default=" and ", description="Delimiter used for splitting")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Derive sequential hop plan from a composite query."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "MultiHopPlannerNode requires a non-empty query"
            raise ValueError(msg)

        raw_parts = [
            part.strip() for part in query.split(self.delimiter) if part.strip()
        ]
        if not raw_parts:
            raw_parts = [query.strip()]

        hops: list[dict[str, Any]] = []
        for index, part in enumerate(raw_parts[: self.max_hops]):
            hops.append(
                {
                    "id": f"hop-{index + 1}",
                    "query": part,
                    "depends_on": hops[-1]["id"] if hops else None,
                }
            )

        return {"plan": hops, "hop_count": len(hops)}
