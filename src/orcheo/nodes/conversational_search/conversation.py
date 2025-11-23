"""Conversation management nodes for conversational search pipelines."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pydantic import ConfigDict, Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.models import ConversationTurn
from orcheo.nodes.registry import NodeMetadata, registry


class BaseMemoryStore(ABC):
    """Abstract interface for conversation memory storage."""

    @abstractmethod
    async def get_session(self, session_id: str) -> dict[str, Any]:
        """Return session payload containing history and metadata."""

    @abstractmethod
    async def save_turn(self, session_id: str, turn: ConversationTurn) -> None:
        """Persist a new conversation turn for the session."""

    @abstractmethod
    async def get_history(self, session_id: str, limit: int) -> list[ConversationTurn]:
        """Return the most recent turns for ``session_id`` up to ``limit``."""

    @abstractmethod
    async def save_summary(self, session_id: str, summary: str) -> None:
        """Persist a textual summary for retention and personalization."""

    @abstractmethod
    async def cleanup(self, session_id: str) -> None:
        """Remove session state and associated metadata."""


class InMemoryMemoryStore(BaseMemoryStore):
    """Simple in-memory memory store for tests and local execution."""

    def __init__(self) -> None:
        """Initialize the session container."""
        self._sessions: dict[str, dict[str, Any]] = {}

    async def get_session(self, session_id: str) -> dict[str, Any]:
        """Return the session payload, creating it when missing."""
        return self._sessions.setdefault(session_id, {"history": [], "summaries": []})

    async def save_turn(self, session_id: str, turn: ConversationTurn) -> None:
        """Append a turn to the session history."""
        session = await self.get_session(session_id)
        session["history"].append(turn)

    async def get_history(self, session_id: str, limit: int) -> list[ConversationTurn]:
        """Return the most recent ``limit`` turns for the session."""
        session = await self.get_session(session_id)
        if limit <= 0:
            return []
        return session["history"][-limit:]

    async def save_summary(self, session_id: str, summary: str) -> None:
        """Persist a summary associated with the session."""
        session = await self.get_session(session_id)
        session["summaries"].append(summary)

    async def cleanup(self, session_id: str) -> None:
        """Remove all in-memory data for the session."""
        self._sessions.pop(session_id, None)


@registry.register(
    NodeMetadata(
        name="ConversationStateNode",
        description="Maintain per-session conversation history with turn budgeting.",
        category="conversational_search",
    )
)
class ConversationStateNode(TaskNode):
    """Node that materializes and updates conversation state."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id_key: str = Field(
        default="session_id",
        description="Key in ``state.inputs`` containing the session id.",
    )
    message_key: str = Field(
        default="user_message",
        description="Key in ``state.inputs`` containing the latest user message.",
    )
    role: Literal["user", "assistant", "system"] = Field(
        default="user", description="Role to attribute to the incoming turn."
    )
    max_turns: int = Field(
        default=50, gt=0, description="Maximum turns to return in history."
    )
    memory_store: BaseMemoryStore = Field(
        default_factory=InMemoryMemoryStore,
        description="Backing store used to persist conversation state.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Persist the latest turn and emit bounded history."""
        del config
        session_id = state.get("inputs", {}).get(self.session_id_key)
        if not isinstance(session_id, str) or not session_id.strip():
            msg = "ConversationStateNode requires a non-empty session_id"
            raise ValueError(msg)

        message = state.get("inputs", {}).get(self.message_key)
        if not isinstance(message, str) or not message.strip():
            msg = "ConversationStateNode requires a non-empty user message"
            raise ValueError(msg)

        turn = ConversationTurn(role=self.role, content=message.strip())
        await self.memory_store.save_turn(session_id, turn)

        history = await self.memory_store.get_history(session_id, self.max_turns)
        metadata = {
            "turn_count": len(
                (await self.memory_store.get_session(session_id))["history"]
            ),
            "session_id": session_id,
        }

        return {
            "session_id": session_id,
            "conversation_history": history,
            "metadata": metadata,
        }


@registry.register(
    NodeMetadata(
        name="ConversationCompressorNode",
        description="Summarize long conversation histories within a token budget.",
        category="conversational_search",
    )
)
class ConversationCompressorNode(TaskNode):
    """Compress conversation history by summarizing older turns."""

    history_result_key: str = Field(
        default="conversation_state",
        description=(
            "Result key holding conversation state output; defaults to "
            "``conversation_state``."
        ),
    )
    history_field: str = Field(
        default="conversation_history",
        description="Field containing conversation turns within the result payload.",
    )
    max_tokens: int = Field(default=800, gt=0, description="Token budget for history.")
    summary_max_tokens: int = Field(
        default=120,
        gt=0,
        description="Maximum tokens to allocate for the summary block.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return compressed conversation history within a token budget."""
        del config
        history_payload = state.get("results", {}).get(self.history_result_key, {})
        history_entries = history_payload.get(self.history_field, history_payload)
        if not isinstance(history_entries, list):
            msg = "Conversation history must be provided as a list"
            raise ValueError(msg)

        turns = [ConversationTurn.model_validate(entry) for entry in history_entries]
        total_tokens = sum(turn.token_count for turn in turns)
        if total_tokens <= self.max_tokens:
            return {
                "conversation_history": turns,
                "summary": None,
                "truncated": False,
                "total_tokens": total_tokens,
            }

        retained: list[ConversationTurn] = []
        truncated: list[ConversationTurn] = []
        running_tokens = 0

        for turn in reversed(turns):
            if running_tokens + turn.token_count > self.max_tokens:
                truncated.append(turn)
                continue
            retained.append(turn)
            running_tokens += turn.token_count

        summary_text = self._build_summary(list(reversed(truncated)))
        summary_turn = ConversationTurn(
            role="system",
            content=f"Summary: {summary_text}",
            metadata={"summary": True, "compressed_turns": len(truncated)},
        )

        compressed_history = [summary_turn] + list(reversed(retained))
        compressed_tokens = sum(turn.token_count for turn in compressed_history)

        return {
            "conversation_history": compressed_history,
            "summary": summary_turn.content,
            "truncated": True,
            "total_tokens": compressed_tokens,
        }

    def _build_summary(self, turns: list[ConversationTurn]) -> str:
        if not turns:
            return ""
        text = "; ".join(f"{turn.role}: {turn.content}" for turn in turns)
        tokens = text.split()
        if len(tokens) <= self.summary_max_tokens:
            return text
        shortened = tokens[: self.summary_max_tokens]
        return " ".join(shortened).rstrip() + "…"


@registry.register(
    NodeMetadata(
        name="TopicShiftDetectorNode",
        description="Detect topic shifts between the latest query and prior turns.",
        category="conversational_search",
    )
)
class TopicShiftDetectorNode(TaskNode):
    """Heuristic detector for topic shifts in a conversation."""

    query_key: str = Field(
        default="query",
        description="Key within ``state.inputs`` holding the latest query.",
    )
    history_result_key: str = Field(
        default="conversation_compressor",
        description="Result key containing compressed history to evaluate.",
    )
    history_field: str = Field(
        default="conversation_history",
        description="Field holding conversation turns within the history payload.",
    )
    min_overlap_ratio: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Minimum token overlap ratio to consider the topic unchanged.",
    )
    shift_markers: set[str] = Field(
        default_factory=lambda: {"new topic", "another question", "switching"},
        description="Phrases that explicitly indicate a topic change.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Detect whether the latest query indicates a topic shift."""
        del config
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "TopicShiftDetectorNode requires a non-empty query string"
            raise ValueError(msg)

        history_payload = state.get("results", {}).get(self.history_result_key, {})
        history_entries = history_payload.get(self.history_field, history_payload)
        if not isinstance(history_entries, list):
            msg = "Conversation history must be provided as a list"
            raise ValueError(msg)

        turns = [ConversationTurn.model_validate(entry) for entry in history_entries]
        last_user_turn = next(
            (turn for turn in reversed(turns) if turn.role == "user"), None
        )
        overlap_ratio = self._overlap_ratio(
            query, last_user_turn.content if last_user_turn else ""
        )
        marker_present = any(marker in query.lower() for marker in self.shift_markers)
        topic_shift = marker_present or overlap_ratio < self.min_overlap_ratio

        reason = "explicit marker" if marker_present else "low overlap"

        return {
            "topic_shift": topic_shift,
            "overlap_ratio": overlap_ratio,
            "last_topic": last_user_turn.content if last_user_turn else None,
            "reason": reason if topic_shift else "stable",
        }

    @staticmethod
    def _overlap_ratio(current: str, previous: str) -> float:
        current_tokens = {token for token in current.lower().split() if token}
        previous_tokens = {token for token in previous.lower().split() if token}
        if not current_tokens or not previous_tokens:
            return 0.0
        intersection = current_tokens & previous_tokens
        return len(intersection) / max(len(current_tokens), 1)


@registry.register(
    NodeMetadata(
        name="QueryClarificationNode",
        description=(
            "Produce clarifying questions when queries are ambiguous or shifted."
        ),
        category="conversational_search",
    )
)
class QueryClarificationNode(TaskNode):
    """Node that emits clarification prompts for ambiguous user queries."""

    query_key: str = Field(
        default="query", description="Key within ``state.inputs`` containing the query."
    )
    topic_result_key: str | None = Field(
        default="topic_detector",
        description="Optional key to read topic shift signals from ``state.results``.",
    )
    ambiguity_pronouns: set[str] = Field(
        default_factory=lambda: {"it", "that", "this", "those", "they"},
        description="Pronouns that often require clarification in isolation.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Emit a clarifying question when ambiguity is detected."""
        del config
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "QueryClarificationNode requires a non-empty query string"
            raise ValueError(msg)

        topic_shift = False
        last_topic: str | None = None
        if self.topic_result_key:
            topic_payload = state.get("results", {}).get(self.topic_result_key, {})
            if isinstance(topic_payload, dict):
                topic_shift = bool(topic_payload.get("topic_shift", False))
                last_topic = topic_payload.get("last_topic")

        needs_clarification = topic_shift or self._has_ambiguous_pronoun(query)
        clarifying_question = None
        if needs_clarification:
            prefix = "I noticed a topic change" if topic_shift else "To clarify"
            context_hint = f" about '{last_topic}'" if last_topic else ""
            clarifying_question = (
                f"{prefix}{context_hint}. Could you specify what you're referring to?"
            )

        return {
            "needs_clarification": needs_clarification,
            "clarifying_question": clarifying_question,
        }

    def _has_ambiguous_pronoun(self, query: str) -> bool:
        tokens = {token.strip(".,?!").lower() for token in query.split()}
        return bool(tokens & self.ambiguity_pronouns)


@registry.register(
    NodeMetadata(
        name="MemorySummarizerNode",
        description="Persist conversation summaries with retention policies.",
        category="conversational_search",
    )
)
class MemorySummarizerNode(TaskNode):
    """Node that stores conversation summaries into a memory store."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id_key: str = Field(
        default="session_id",
        description="Key within ``state.inputs`` for the session id.",
    )
    summary_result_key: str = Field(
        default="conversation_compressor",
        description="Result key containing the generated summary text.",
    )
    summary_field: str = Field(
        default="summary",
        description="Field holding the summary string inside the result payload.",
    )
    retention_summaries: int = Field(
        default=5,
        gt=0,
        description="Maximum number of summaries to retain per session.",
    )
    memory_store: BaseMemoryStore = Field(
        default_factory=InMemoryMemoryStore,
        description="Backing store used to persist summaries.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Persist summaries while enforcing retention policies."""
        del config
        session_id = state.get("inputs", {}).get(self.session_id_key)
        if not isinstance(session_id, str) or not session_id.strip():
            msg = "MemorySummarizerNode requires a non-empty session_id"
            raise ValueError(msg)

        summary_payload = state.get("results", {}).get(self.summary_result_key, {})
        summary_text = summary_payload.get(self.summary_field)
        if not isinstance(summary_text, str) or not summary_text.strip():
            msg = "MemorySummarizerNode requires a non-empty summary to persist"
            raise ValueError(msg)

        await self.memory_store.save_summary(session_id, summary_text.strip())
        session = await self.memory_store.get_session(session_id)
        summaries: list[str] = session.get("summaries", [])
        if len(summaries) > self.retention_summaries:
            excess = len(summaries) - self.retention_summaries
            del summaries[0:excess]

        return {
            "session_id": session_id,
            "summary": summary_text.strip(),
            "summary_count": len(summaries),
        }
