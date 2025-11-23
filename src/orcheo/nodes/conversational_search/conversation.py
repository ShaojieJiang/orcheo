"""Conversation management nodes for conversational search pipelines."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.models import (
    ConversationSession,
    ConversationTurn,
    MemorySummary,
)
from orcheo.nodes.registry import NodeMetadata, registry


class BaseMemoryStore(ABC, BaseModel):
    """Abstract interface for storing conversation state and summaries."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @abstractmethod
    async def load_session(self, session_id: str) -> ConversationSession | None:
        """Return the stored session for ``session_id`` if present."""

    @abstractmethod
    async def save_session(self, session: ConversationSession) -> None:
        """Persist ``session`` with its updated history and metadata."""

    @abstractmethod
    async def append_summary(
        self, summary: MemorySummary, retention_count: int | None = None
    ) -> None:
        """Store a summary while respecting optional retention limits."""

    @abstractmethod
    async def list_summaries(self, session_id: str) -> list[MemorySummary]:
        """Return stored summaries for ``session_id`` in chronological order."""

    @abstractmethod
    async def cleanup(self, session_id: str) -> None:
        """Remove all persisted state for ``session_id``."""


class InMemoryMemoryStore(BaseMemoryStore):
    """Simple in-memory memory store suitable for testing and local runs."""

    sessions: dict[str, ConversationSession] = Field(default_factory=dict)
    summaries: dict[str, list[MemorySummary]] = Field(default_factory=dict)

    async def load_session(self, session_id: str) -> ConversationSession | None:
        """Return the session payload for ``session_id`` if present."""
        return self.sessions.get(session_id)

    async def save_session(self, session: ConversationSession) -> None:
        """Persist the provided session in the in-memory store."""
        self.sessions[session.session_id] = session

    async def append_summary(
        self, summary: MemorySummary, retention_count: int | None = None
    ) -> None:
        """Store ``summary`` while optionally trimming to ``retention_count``."""
        entries = self.summaries.setdefault(summary.session_id, [])
        entries.append(summary)
        if retention_count and len(entries) > retention_count:
            del entries[0 : len(entries) - retention_count]

    async def list_summaries(self, session_id: str) -> list[MemorySummary]:
        """Return summaries for ``session_id`` ordered oldest to newest."""
        return list(self.summaries.get(session_id, []))

    async def cleanup(self, session_id: str) -> None:
        """Remove all stored data for ``session_id``."""
        self.sessions.pop(session_id, None)
        self.summaries.pop(session_id, None)


@registry.register(
    NodeMetadata(
        name="ConversationStateNode",
        description="Manage per-session conversation state and history.",
        category="conversational_search",
    )
)
class ConversationStateNode(TaskNode):
    """Load and update conversation state within a memory store."""

    session_id_key: str = Field(
        default="session_id",
        description="Key within ``state.inputs`` containing the session identifier.",
    )
    user_message_key: str = Field(
        default="user_message",
        description="Key within ``state.inputs`` holding the latest user message.",
    )
    assistant_message_key: str = Field(
        default="assistant_message",
        description="Optional key for the latest assistant message to append.",
    )
    history_key: str | None = Field(
        default=None,
        description="Optional key in ``state.inputs`` containing a history payload.",
    )
    max_turns: int = Field(
        default=50, gt=0, description="Maximum number of turns to retain per session."
    )
    memory_store: BaseMemoryStore = Field(
        default_factory=InMemoryMemoryStore,
        description="Backing store used to persist conversation sessions.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Load the session from memory and append new turns."""
        session_id = state.get("inputs", {}).get(self.session_id_key)
        if not isinstance(session_id, str) or not session_id.strip():
            msg = "ConversationStateNode requires a non-empty session_id"
            raise ValueError(msg)

        session = await self._load_or_initialize(session_id)
        provided_history = self._extract_history(state)
        if provided_history is not None:
            session.history = provided_history

        self._append_turns(session, state)
        session.trim_history(self.max_turns)
        session.metadata["turn_count"] = len(session.history)

        await self.memory_store.save_session(session)
        return {
            "session_id": session.session_id,
            "history": session.history,
            "metadata": session.metadata,
            "turn_count": len(session.history),
        }

    async def _load_or_initialize(self, session_id: str) -> ConversationSession:
        existing = await self.memory_store.load_session(session_id)
        if existing is not None:
            return existing
        return ConversationSession(session_id=session_id)

    def _extract_history(self, state: State) -> list[ConversationTurn] | None:
        if not self.history_key:
            return None
        history_payload = state.get("inputs", {}).get(self.history_key)
        if history_payload is None:
            return None
        if not isinstance(history_payload, list):
            msg = "history must be provided as a list of turns"
            raise ValueError(msg)
        return [ConversationTurn.model_validate(turn) for turn in history_payload]

    def _append_turns(self, session: ConversationSession, state: State) -> None:
        inputs = state.get("inputs", {})
        roles: tuple[tuple[str, Literal["user", "assistant"]], ...] = (
            (self.user_message_key, "user"),
            (self.assistant_message_key, "assistant"),
        )
        for key, role in roles:
            message = inputs.get(key)
            if isinstance(message, str) and message.strip():
                turn = ConversationTurn(role=role, content=message.strip())
                session.append_turn(turn)


@registry.register(
    NodeMetadata(
        name="ConversationCompressorNode",
        description="Summarize conversation history within a token budget.",
        category="conversational_search",
    )
)
class ConversationCompressorNode(TaskNode):
    """Generate a concise summary of conversation history."""

    conversation_state_key: str = Field(
        default="conversation_state",
        description="Key in ``state.results`` where conversation state is stored.",
    )
    history_field: str = Field(
        default="history",
        description="Field name containing the history list within the payload.",
    )
    max_tokens: int = Field(
        default=120, gt=0, description="Maximum token budget for the summary."
    )
    preserve_recent: int = Field(
        default=2,
        ge=0,
        description="Number of most recent turns to always retain verbatim.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Compress conversation history into a token-budgeted summary."""
        payload = state.get("results", {}).get(self.conversation_state_key)
        if payload is None:
            msg = "ConversationCompressorNode requires conversation state results"
            raise ValueError(msg)

        history_payload = payload.get(self.history_field)
        if not isinstance(history_payload, list):
            msg = "conversation history must be a list"
            raise ValueError(msg)

        turns = [ConversationTurn.model_validate(turn) for turn in history_payload]
        summary, token_count, truncated = self._summarize(turns)
        retained = turns[-self.preserve_recent :] if self.preserve_recent else []

        return {
            "summary": summary,
            "token_count": token_count,
            "truncated": truncated,
            "retained_history": retained,
        }

    def _summarize(self, turns: list[ConversationTurn]) -> tuple[str, int, bool]:
        if not turns:
            return "", 0, False

        parts: list[str] = []
        token_count = 0
        truncated = False
        for turn in turns:
            prefix = f"{turn.role}: "
            content = turn.content.strip()
            candidate = f"{prefix}{content}"
            candidate_tokens = self._token_count(candidate)
            if token_count + candidate_tokens > self.max_tokens:
                truncated = True
                break
            parts.append(candidate)
            token_count += candidate_tokens

        summary = " ".join(parts)
        return summary, token_count, truncated

    @staticmethod
    def _token_count(text: str) -> int:
        return len(text.split())


@registry.register(
    NodeMetadata(
        name="TopicShiftDetectorNode",
        description="Detect whether the latest query diverges from prior turns.",
        category="conversational_search",
    )
)
class TopicShiftDetectorNode(TaskNode):
    """Heuristic detector for conversation topic shifts."""

    query_key: str = Field(
        default="query", description="Key within ``state.inputs`` holding the query."
    )
    conversation_state_key: str = Field(
        default="conversation_state",
        description="Key in ``state.results`` providing conversation history.",
    )
    similarity_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Minimum token overlap ratio to consider on-topic.",
    )
    shift_phrases: set[str] = Field(
        default_factory=lambda: {
            "different topic",
            "unrelated",
            "switch gears",
            "change topic",
        },
        description="Phrases that explicitly indicate a topic change.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return topic shift signals for the current query."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "TopicShiftDetectorNode requires a non-empty query"
            raise ValueError(msg)

        history_payload = state.get("results", {}).get(self.conversation_state_key, {})
        history = (
            history_payload.get("history", [])
            if isinstance(history_payload, dict)
            else []
        )
        turns = [ConversationTurn.model_validate(turn) for turn in history]
        last_message = self._last_user_turn(turns)

        similarity = self._similarity(last_message, query)
        explicit_shift = self._contains_shift_phrase(query)
        topic_shift = explicit_shift or (
            last_message is not None and similarity < self.similarity_threshold
        )

        return {
            "topic_shift": topic_shift,
            "similarity": similarity,
            "last_message": last_message,
            "reason": "explicit" if explicit_shift else "similarity",
        }

    @staticmethod
    def _last_user_turn(turns: list[ConversationTurn]) -> str | None:
        for turn in reversed(turns):
            if turn.role == "user" and turn.content.strip():
                return turn.content.strip()
        return None

    def _similarity(self, previous: str | None, current: str) -> float:
        if previous is None:
            return 1.0

        left_tokens = set(previous.lower().split())
        right_tokens = set(current.lower().split())
        if not left_tokens or not right_tokens:
            return 0.0

        intersection = len(left_tokens & right_tokens)
        union = len(left_tokens | right_tokens)
        return intersection / union if union else 0.0

    def _contains_shift_phrase(self, query: str) -> bool:
        normalized = query.lower()
        return any(phrase in normalized for phrase in self.shift_phrases)


@registry.register(
    NodeMetadata(
        name="QueryClarificationNode",
        description="Generate clarifying prompts for ambiguous or shifting queries.",
        category="conversational_search",
    )
)
class QueryClarificationNode(TaskNode):
    """Emit a clarification prompt when routing confidence is low."""

    query_key: str = Field(
        default="query", description="Key within ``state.inputs`` holding the query."
    )
    topic_signal_key: str = Field(
        default="topic_shift_detector",
        description="Key in ``state.results`` containing topic shift signals.",
    )
    min_query_words: int = Field(
        default=4, gt=0, description="Minimum words before treating a query as clear."
    )
    pronoun_set: set[str] = Field(
        default_factory=lambda: {"it", "that", "this", "those"},
        description="Pronouns that can trigger clarification prompts.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Generate a clarification prompt when the query seems ambiguous."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "QueryClarificationNode requires a non-empty query"
            raise ValueError(msg)

        topic_signal = state.get("results", {}).get(self.topic_signal_key, {})
        shift_detected = (
            bool(topic_signal.get("topic_shift"))
            if isinstance(topic_signal, dict)
            else False
        )

        needs_clarification = self._requires_clarification(query, shift_detected)
        prompt = None
        if needs_clarification:
            prompt = self._build_prompt(query, shift_detected)

        return {"needs_clarification": needs_clarification, "prompt": prompt}

    def _requires_clarification(self, query: str, shift_detected: bool) -> bool:
        tokens = query.strip().split()
        if len(tokens) < self.min_query_words:
            return True
        if shift_detected:
            return True
        return any(token.lower() in self.pronoun_set for token in tokens)

    @staticmethod
    def _build_prompt(query: str, shift_detected: bool) -> str:
        if shift_detected:
            return (
                "It sounds like you're changing topics. Could you clarify what "
                "you'd like to explore next?"
            )
        return (
            "I want to make sure I answer correctly. Could you provide more "
            f"detail about '{query.strip()}'?"
        )


@registry.register(
    NodeMetadata(
        name="MemorySummarizerNode",
        description="Persist episodic conversation summaries into memory stores.",
        category="conversational_search",
    )
)
class MemorySummarizerNode(TaskNode):
    """Write concise summaries to the configured memory store."""

    session_id_key: str = Field(
        default="session_id",
        description="Key within ``state.inputs`` that contains the session id.",
    )
    conversation_state_key: str = Field(
        default="conversation_state",
        description="Key in ``state.results`` that holds conversation state results.",
    )
    summary_source_key: str = Field(
        default="conversation_compressor",
        description="Key in ``state.results`` providing a prepared summary.",
    )
    retention_count: int = Field(
        default=3,
        gt=0,
        description="Maximum number of summaries to retain per session.",
    )
    min_turns: int = Field(
        default=2,
        ge=1,
        description="Minimum turns required before persisting a summary entry.",
    )
    memory_store: BaseMemoryStore = Field(
        default_factory=InMemoryMemoryStore,
        description="Backing store used to persist summaries and state.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Persist a summary for the provided session into the memory store."""
        session_id = state.get("inputs", {}).get(self.session_id_key)
        if not isinstance(session_id, str) or not session_id.strip():
            msg = "MemorySummarizerNode requires a non-empty session_id"
            raise ValueError(msg)

        history = self._resolve_history(state)
        if len(history) < self.min_turns:
            msg = "Not enough conversation turns to summarize"
            raise ValueError(msg)

        summary_text = self._resolve_summary(state, history)
        summary = MemorySummary(
            session_id=session_id,
            summary=summary_text,
            metadata={"turns": len(history)},
        )
        await self.memory_store.append_summary(
            summary, retention_count=self.retention_count
        )
        return {
            "session_id": session_id,
            "summary": summary.summary,
            "retained": await self.memory_store.list_summaries(session_id),
        }

    def _resolve_history(self, state: State) -> list[ConversationTurn]:
        payload = state.get("results", {}).get(self.conversation_state_key)
        if not isinstance(payload, dict):
            msg = "Conversation state payload missing for summarization"
            raise ValueError(msg)
        history_payload = payload.get("history", [])
        if not isinstance(history_payload, list):
            msg = "history must be provided as a list"
            raise ValueError(msg)
        return [ConversationTurn.model_validate(turn) for turn in history_payload]

    def _resolve_summary(self, state: State, history: list[ConversationTurn]) -> str:
        summary_payload = state.get("results", {}).get(self.summary_source_key)
        if isinstance(summary_payload, dict) and summary_payload.get("summary"):
            return str(summary_payload["summary"])

        snippets = []
        for turn in history[-3:]:
            snippets.append(f"{turn.role}: {turn.content}")
        return " ".join(snippets)
