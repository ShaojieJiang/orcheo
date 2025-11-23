"""Conversation management and memory nodes for conversational search."""

from __future__ import annotations
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field, model_validator
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


class MemoryTurn(BaseModel):
    """Representation of a single conversation turn."""

    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _trim_content(self) -> MemoryTurn:
        self.content = self.content.strip()
        if not self.content:
            msg = "MemoryTurn content cannot be empty"
            raise ValueError(msg)
        return self


class BaseMemoryStore(ABC, BaseModel):
    """Abstract contract for conversation memory backends."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @abstractmethod
    async def load_history(
        self, session_id: str, limit: int | None = None
    ) -> list[MemoryTurn]:
        """Return turns for ``session_id`` while honoring ``limit`` when provided."""

    @abstractmethod
    async def append_turn(self, session_id: str, turn: MemoryTurn) -> None:
        """Persist ``turn`` for the provided ``session_id``."""

    @abstractmethod
    async def prune(self, session_id: str, max_turns: int | None = None) -> None:
        """Remove oldest turns to enforce ``max_turns`` when specified."""

    @abstractmethod
    async def write_summary(
        self, session_id: str, summary: str, ttl_seconds: int | None = None
    ) -> None:
        """Persist ``summary`` with optional TTL."""

    @abstractmethod
    async def get_summary(self, session_id: str) -> str | None:
        """Return a persisted summary if present and not expired."""

    @abstractmethod
    async def clear(self, session_id: str) -> None:
        """Remove all state for ``session_id``."""


class InMemoryMemoryStore(BaseMemoryStore):
    """Simple in-memory store suited for local development and tests."""

    sessions: dict[str, list[MemoryTurn]] = Field(default_factory=dict)
    summaries: dict[str, tuple[str, float | None]] = Field(default_factory=dict)

    async def load_history(
        self, session_id: str, limit: int | None = None
    ) -> list[MemoryTurn]:
        """Return stored turns for ``session_id`` with optional tail ``limit``."""
        history = self.sessions.get(session_id, [])
        if limit is None:
            return list(history)
        return list(history[-limit:])

    async def append_turn(self, session_id: str, turn: MemoryTurn) -> None:
        """Append ``turn`` to the session history."""
        self.sessions.setdefault(session_id, []).append(turn)

    async def prune(self, session_id: str, max_turns: int | None = None) -> None:
        """Trim history to ``max_turns`` turns when provided."""
        if max_turns is None:
            return
        history = self.sessions.get(session_id)
        if history is None:
            return
        if len(history) > max_turns:
            self.sessions[session_id] = history[-max_turns:]

    async def write_summary(
        self, session_id: str, summary: str, ttl_seconds: int | None = None
    ) -> None:
        """Store ``summary`` with optional expiration."""
        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        self.summaries[session_id] = (summary, expires_at)

    async def get_summary(self, session_id: str) -> str | None:
        """Return summary if available and not expired."""
        entry = self.summaries.get(session_id)
        if entry is None:
            return None
        summary, expires_at = entry
        if expires_at is not None and expires_at < time.time():
            await self.clear(session_id)
            return None
        return summary

    async def clear(self, session_id: str) -> None:
        """Delete stored turns and summaries for ``session_id``."""
        self.sessions.pop(session_id, None)
        self.summaries.pop(session_id, None)


@registry.register(
    NodeMetadata(
        name="ConversationStateNode",
        description="Load and persist conversation history for a session.",
        category="conversational_search",
    )
)
class ConversationStateNode(TaskNode):
    """Manage per-session conversation turns with basic limits."""

    session_id_key: str = Field(
        default="session_id", description="Key in ``state.inputs`` with the session id."
    )
    user_message_key: str = Field(
        default="user_message",
        description="Key containing the latest user message to append.",
    )
    assistant_message_key: str = Field(
        default="assistant_message",
        description="Optional key containing an assistant response to persist.",
    )
    memory_store: BaseMemoryStore = Field(
        default_factory=InMemoryMemoryStore,
        description="Backing store used to load and persist conversation turns.",
    )
    max_turns: int = Field(
        default=50, gt=0, description="Maximum number of turns retained per session."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Load history, append new turns, and return updated session context."""
        session_id_raw = state.get("inputs", {}).get(self.session_id_key)
        if not isinstance(session_id_raw, str) or not session_id_raw.strip():
            msg = "ConversationStateNode requires a non-empty session id"
            raise ValueError(msg)
        session_id = session_id_raw.strip()

        history = await self.memory_store.load_history(session_id, limit=self.max_turns)

        append_candidates: list[tuple[str, Literal["user", "assistant"]]] = [
            (self.user_message_key, "user"),
            (self.assistant_message_key, "assistant"),
        ]
        for key, role in append_candidates:
            message = state.get("inputs", {}).get(key)
            if isinstance(message, str) and message.strip():
                turn = MemoryTurn(role=role, content=message)
                await self.memory_store.append_turn(session_id, turn)

        await self.memory_store.prune(session_id, max_turns=self.max_turns)
        history = await self.memory_store.load_history(session_id, limit=self.max_turns)
        summary = await self.memory_store.get_summary(session_id)

        return {
            "session_id": session_id,
            "conversation_history": [turn.model_dump() for turn in history],
            "turn_count": len(history),
            "summary": summary,
            "truncated": len(history) >= self.max_turns,
        }


@registry.register(
    NodeMetadata(
        name="ConversationCompressorNode",
        description="Summarize and budget a conversation history for downstream use.",
        category="conversational_search",
    )
)
class ConversationCompressorNode(TaskNode):
    """Reduce a conversation history to fit a token budget."""

    source_result_key: str = Field(
        default="conversation_state",
        description="Key within ``state.results`` containing conversation payloads.",
    )
    history_key: str = Field(
        default="conversation_history",
        description="Field holding turn dictionaries within ``source_result_key``.",
    )
    max_tokens: int = Field(
        default=120,
        gt=0,
        description="Maximum whitespace token budget for the compressed history.",
    )
    preserve_recent: int = Field(
        default=2,
        ge=0,
        description="Number of most recent turns that should always be retained.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return compressed conversation context within the configured token budget."""
        source = state.get("results", {}).get(self.source_result_key, {})
        history_payload = self._extract_history(source)
        turns = [MemoryTurn.model_validate(turn) for turn in history_payload]
        if not turns:
            msg = "ConversationCompressorNode requires at least one turn to compress"
            raise ValueError(msg)

        compressed: list[MemoryTurn] = []
        token_total = 0
        truncated = False

        for index, turn in enumerate(reversed(turns)):
            tokens = self._token_count(turn.content)
            should_keep = (
                index < self.preserve_recent or token_total + tokens <= self.max_tokens
            )
            if not should_keep:
                truncated = True
                continue
            compressed.append(turn)
            token_total += tokens

        compressed.reverse()
        summary_source = compressed or turns
        summary = self._summarize(summary_source, token_limit=self.max_tokens)

        return {
            "compressed_history": [turn.model_dump() for turn in compressed],
            "summary": summary,
            "total_tokens": token_total,
            "truncated": truncated,
        }

    def _extract_history(self, source: Any) -> list[dict[str, Any]]:
        if isinstance(source, dict) and self.history_key in source:
            history_payload = source[self.history_key]
        else:
            history_payload = source
        if not isinstance(history_payload, list):
            msg = "conversation_history must be provided as a list"
            raise ValueError(msg)
        return history_payload

    @staticmethod
    def _token_count(text: str) -> int:
        return len(text.split())

    def _summarize(self, turns: Iterable[MemoryTurn], token_limit: int) -> str:
        buffer: list[str] = []
        token_total = 0
        for turn in turns:
            tokens = self._token_count(turn.content)
            entry = f"{turn.role}: {turn.content}"
            if token_total + tokens > token_limit:
                if not buffer:
                    snippet_tokens = turn.content.split()[: max(token_limit, 1)]
                    snippet = " ".join(snippet_tokens).strip()
                    entry = f"{turn.role}: {snippet}..." if snippet else "..."
                    buffer.append(entry)
                else:
                    buffer.append("...")
                break
            buffer.append(entry)
            token_total += tokens
        return " | ".join(buffer)


@registry.register(
    NodeMetadata(
        name="TopicShiftDetectorNode",
        description=(
            "Detect whether a new query diverges from recent conversation context."
        ),
        category="conversational_search",
    )
)
class TopicShiftDetectorNode(TaskNode):
    """Heuristic detector for topic shifts using token overlap."""

    query_key: str = Field(
        default="query", description="Key holding the active query string."
    )
    source_result_key: str = Field(
        default="conversation_state",
        description="Key within ``state.results`` providing conversation context.",
    )
    history_key: str = Field(
        default="conversation_history",
        description="Field containing turns used for topic comparison.",
    )
    similarity_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Minimum token overlap required to avoid a topic shift flag.",
    )
    recent_turns: int = Field(
        default=3,
        ge=1,
        description="Number of turns to consider for similarity scoring.",
    )

    stopwords: set[str] = Field(
        default_factory=lambda: {
            "the",
            "a",
            "an",
            "and",
            "or",
            "of",
            "it",
            "this",
            "that",
            "to",
            "for",
        },
        description="Stopwords removed before similarity scoring.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Score the new query against recent turns and flag topic shifts."""
        query_raw = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query_raw, str) or not query_raw.strip():
            msg = "TopicShiftDetectorNode requires a non-empty query"
            raise ValueError(msg)
        query = query_raw.strip()

        history_payload = state.get("results", {}).get(self.source_result_key, {})
        turns_raw = self._extract_turns(history_payload)
        if not turns_raw:
            return {
                "is_shift": False,
                "similarity": 1.0,
                "route": "continue",
                "reason": "no_history",
            }

        window = [MemoryTurn.model_validate(turn) for turn in turns_raw][
            -self.recent_turns :
        ]
        similarity = self._jaccard_similarity(query, window)
        is_shift = similarity < self.similarity_threshold
        route = "clarify" if is_shift else "continue"

        return {
            "is_shift": is_shift,
            "similarity": similarity,
            "route": route,
            "reason": "low_overlap" if is_shift else "aligned",
        }

    def _extract_turns(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict) and self.history_key in payload:
            turns = payload[self.history_key]
        else:
            turns = payload
        if turns is None:
            return []
        if not isinstance(turns, list):
            msg = "conversation_history must be provided as a list"
            raise ValueError(msg)
        return turns

    def _tokenize(self, text: str) -> set[str]:
        tokens = {token.lower() for token in text.split()}
        return {token for token in tokens if token and token not in self.stopwords}

    def _jaccard_similarity(self, query: str, turns: Iterable[MemoryTurn]) -> float:
        query_tokens = self._tokenize(query)
        history_tokens: set[str] = set()
        for turn in turns:
            history_tokens |= self._tokenize(turn.content)
        if not history_tokens or not query_tokens:
            return 0.0
        intersection = len(query_tokens & history_tokens)
        union = len(query_tokens | history_tokens)
        return intersection / union if union else 0.0


@registry.register(
    NodeMetadata(
        name="QueryClarificationNode",
        description="Generate clarifying prompts when ambiguity is detected.",
        category="conversational_search",
    )
)
class QueryClarificationNode(TaskNode):
    """Produce clarifying questions based on the active query and context."""

    query_key: str = Field(
        default="query", description="Key within ``state.inputs`` holding the query."
    )
    history_key: str = Field(
        default="conversation_history",
        description="Field used to retrieve conversation history if present.",
    )
    max_questions: int = Field(
        default=2, ge=1, description="Maximum number of clarification prompts to emit."
    )

    ambiguous_markers: set[str] = Field(
        default_factory=lambda: {"it", "that", "those", "they", "this"},
        description="Tokens that often signal ambiguity requiring clarification.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Generate clarifying questions when the query appears ambiguous."""
        query_raw = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query_raw, str) or not query_raw.strip():
            msg = "QueryClarificationNode requires a non-empty query"
            raise ValueError(msg)
        query = query_raw.strip()

        history = state.get("results", {}).get(self.history_key)
        context_hint = ""
        if isinstance(history, dict) and "summary" in history:
            context_hint = history.get("summary") or ""
        elif isinstance(history, list) and history:
            context_hint = history[-1] if isinstance(history[-1], str) else ""

        clarifications = self._build_questions(query, context_hint)

        return {
            "clarifications": clarifications[: self.max_questions],
            "needs_clarification": bool(clarifications),
            "context_hint": context_hint or None,
        }

    def _build_questions(self, query: str, context_hint: str) -> list[str]:
        questions: list[str] = []
        tokens = {token.lower().strip(".,?!") for token in query.split()}
        if tokens & self.ambiguous_markers:
            questions.append("What specific item are you referring to?")
        if "or" in tokens:
            questions.append("Which option should I focus on first?")
        if not questions:
            focus = context_hint or "your last request"
            questions.append(f"Can you provide more detail about {focus}?")
        return questions


@registry.register(
    NodeMetadata(
        name="MemorySummarizerNode",
        description="Persist a compact conversation summary into the memory store.",
        category="conversational_search",
    )
)
class MemorySummarizerNode(TaskNode):
    """Write a conversation summary to the configured memory store."""

    session_id_key: str = Field(
        default="session_id", description="Key containing the active session id."
    )
    source_result_key: str = Field(
        default="conversation_state",
        description="Key within ``state.results`` providing conversation context.",
    )
    history_key: str = Field(
        default="conversation_history",
        description="Field inside ``source_result_key`` with turn payloads.",
    )
    summary_field: str = Field(
        default="summary",
        description="Optional existing summary to persist if present.",
    )
    memory_store: BaseMemoryStore = Field(
        default_factory=InMemoryMemoryStore,
        description="Backing store used to persist summaries.",
    )
    retention_seconds: int | None = Field(
        default=3600,
        description="TTL for persisted summaries; ``None`` disables expiration.",
    )
    max_summary_tokens: int = Field(
        default=180,
        gt=0,
        description="Token budget when generating summaries from turns.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Persist a compact summary of the current conversation state."""
        session_id_raw = state.get("inputs", {}).get(self.session_id_key)
        if not isinstance(session_id_raw, str) or not session_id_raw.strip():
            msg = "MemorySummarizerNode requires a non-empty session id"
            raise ValueError(msg)
        session_id = session_id_raw.strip()

        context = state.get("results", {}).get(self.source_result_key, {})
        summary = None
        if isinstance(context, dict):
            summary = context.get(self.summary_field)
            history_payload = context.get(self.history_key, [])
        else:
            history_payload = []

        turns = [MemoryTurn.model_validate(item) for item in history_payload]
        if summary is None:
            summary = self._summarize(turns)

        if self.retention_seconds is not None and self.retention_seconds <= 0:
            msg = "retention_seconds must be positive when provided"
            raise ValueError(msg)

        await self.memory_store.write_summary(
            session_id, summary=summary, ttl_seconds=self.retention_seconds
        )

        return {
            "summary": summary,
            "turns_summarized": len(turns),
            "ttl_seconds": self.retention_seconds,
        }

    def _summarize(self, turns: list[MemoryTurn]) -> str:
        if not turns:
            return "No conversation history yet."
        buffer: list[str] = []
        token_total = 0
        for turn in turns:
            tokens = len(turn.content.split())
            if token_total + tokens > self.max_summary_tokens:
                buffer.append("...")
                break
            buffer.append(f"{turn.role}: {turn.content}")
            token_total += tokens
        return " | ".join(buffer)
