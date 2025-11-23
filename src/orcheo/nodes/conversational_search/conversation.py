"""Conversation management nodes for conversational search."""

from __future__ import annotations
import re
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import ConfigDict, Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.memory import BaseMemoryStore, Turn
from orcheo.nodes.conversational_search.models import ConversationTurn
from orcheo.nodes.registry import NodeMetadata, registry


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"\b\w+\b", text.lower())
    stopwords = {"the", "a", "an", "and", "or", "of", "to", "in"}
    return {token for token in tokens if token not in stopwords}


@registry.register(
    NodeMetadata(
        name="ConversationStateNode",
        description="Normalize and retain conversation history with metadata.",
        category="conversational_search",
    )
)
class ConversationStateNode(TaskNode):
    """Aggregate conversation history and enforce turn budgets."""

    session_id_key: str = Field(
        default="session_id",
        description="Key in ``state.inputs`` containing the session identifier.",
    )
    history_key: str = Field(
        default="history",
        description="Key in ``state.inputs`` that holds prior turns.",
    )
    user_message_key: str = Field(
        default="user_message",
        description="Key in ``state.inputs`` holding the latest user message.",
    )
    assistant_message_key: str = Field(
        default="assistant_message",
        description="Optional assistant reply to append to the state.",
    )
    max_turns: int = Field(default=50, gt=0, description="Maximum turns to retain.")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return normalized conversation history bounded by ``max_turns``."""
        session_id = state.get("inputs", {}).get(self.session_id_key)
        if not isinstance(session_id, str) or not session_id.strip():
            msg = "ConversationStateNode requires a non-empty session_id"
            raise ValueError(msg)

        raw_history = state.get("inputs", {}).get(self.history_key, []) or []
        if not isinstance(raw_history, list):
            msg = "history must be a list of conversation turns"
            raise ValueError(msg)

        turns = [ConversationTurn.model_validate(item) for item in raw_history]

        user_message = state.get("inputs", {}).get(self.user_message_key)
        if isinstance(user_message, str) and user_message.strip():
            turns.append(
                ConversationTurn(role="user", content=user_message.strip(), metadata={})
            )

        assistant_message = state.get("inputs", {}).get(self.assistant_message_key)
        if isinstance(assistant_message, str) and assistant_message.strip():
            turns.append(
                ConversationTurn(
                    role="assistant", content=assistant_message.strip(), metadata={}
                )
            )

        trimmed = turns[-self.max_turns :]
        total_tokens = sum(turn.token_count for turn in trimmed)

        return {
            "session_id": session_id,
            "conversation_history": trimmed,
            "metadata": {"turn_count": len(trimmed), "total_tokens": total_tokens},
        }


@registry.register(
    NodeMetadata(
        name="ConversationCompressorNode",
        description="Summarize conversation history with a token budget.",
        category="conversational_search",
    )
)
class ConversationCompressorNode(TaskNode):
    """Compress conversation history into a short summary."""

    history_key: str = Field(
        default="conversation_history",
        description="Key containing the list of :class:`ConversationTurn` objects.",
    )
    max_tokens: int = Field(
        default=120,
        gt=0,
        description="Maximum approximate tokens to keep when summarizing.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return a compressed summary and retained turns under ``max_tokens``."""
        history = state.get("results", {}).get(self.history_key)
        if history is None:
            history = self._extract_history_from_results(state.get("results", {}))

        if history is None:
            history = state.get("inputs", {}).get(self.history_key)

        if history is None:
            msg = "ConversationCompressorNode requires conversation_history"
            raise ValueError(msg)

        if not isinstance(history, list):
            msg = "conversation_history must be provided as a list"
            raise ValueError(msg)

        turns = [ConversationTurn.model_validate(item) for item in history]
        retained: list[ConversationTurn] = []
        total_tokens = 0
        truncated = False

        for turn in reversed(turns):
            tokens = turn.token_count
            if total_tokens + tokens > self.max_tokens:
                truncated = True
                break
            retained.append(turn)
            total_tokens += tokens

        retained.reverse()
        summary = self._build_summary(retained)

        return {
            "summary": summary,
            "retained_turns": retained,
            "truncated": truncated,
            "total_tokens": total_tokens,
        }

    @staticmethod
    def _extract_history_from_results(results: dict[str, Any]) -> list[Any] | None:
        for value in results.values():
            if isinstance(value, dict) and "conversation_history" in value:
                return value.get("conversation_history")
        return None

    @staticmethod
    def _build_summary(turns: list[ConversationTurn]) -> str:
        parts = [f"{turn.role}: {turn.content}" for turn in turns]
        return " | ".join(parts)


@registry.register(
    NodeMetadata(
        name="TopicShiftDetectorNode",
        description="Detect topic shifts between the current query and history.",
        category="conversational_search",
    )
)
class TopicShiftDetectorNode(TaskNode):
    """Detect when the current query diverges from recent history."""

    query_key: str = Field(
        default="query", description="Key holding the active user query."
    )
    history_key: str = Field(
        default="conversation_history",
        description="Key holding prior :class:`ConversationTurn` entries.",
    )
    overlap_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Minimum token overlap to consider the topic unchanged.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return topic shift signals derived from lexical overlap."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "TopicShiftDetectorNode requires a non-empty query"
            raise ValueError(msg)

        history = state.get("results", {}).get(self.history_key)
        if history is None:
            history = state.get("inputs", {}).get(self.history_key, [])

        if not isinstance(history, list):
            msg = "conversation_history must be provided as a list"
            raise ValueError(msg)

        turns = [ConversationTurn.model_validate(item) for item in history]
        last_user = next(
            (turn for turn in reversed(turns) if turn.role == "user"), None
        )

        current_tokens = _tokenize(query)
        reference = last_user.content if last_user else None
        previous_tokens = _tokenize(reference) if reference else set()

        if not current_tokens or not previous_tokens:
            return {"topic_shift": False, "overlap": 0.0, "reference": reference}

        overlap = len(current_tokens & previous_tokens) / max(len(current_tokens), 1)
        topic_shift = overlap < self.overlap_threshold

        return {
            "topic_shift": topic_shift,
            "overlap": overlap,
            "reference": reference,
        }


@registry.register(
    NodeMetadata(
        name="QueryClarificationNode",
        description=(
            "Emit a clarification prompt when ambiguity or topic shifts are detected."
        ),
        category="conversational_search",
    )
)
class QueryClarificationNode(TaskNode):
    """Produce clarifying guidance when routing requires more context."""

    query_key: str = Field(
        default="query", description="Key containing the current user query."
    )
    topic_shift_key: str = Field(
        default="topic_shift", description="Key containing the topic shift flag."
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return a clarifying question suggestion when needed."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "QueryClarificationNode requires a non-empty query"
            raise ValueError(msg)

        topic_signal = state.get("results", {}).get(self.topic_shift_key)
        if isinstance(topic_signal, dict) and "topic_shift" in topic_signal:
            topic_shift = bool(topic_signal.get("topic_shift"))
        elif isinstance(topic_signal, bool):
            topic_shift = topic_signal
        else:
            topic_shift = False

        ambiguous = self._is_ambiguous(query)
        needs_clarification = topic_shift or ambiguous

        prompt = (
            "Can you clarify what you'd like to explore next?"
            if needs_clarification
            else "Proceed with retrieval."
        )

        return {
            "needs_clarification": needs_clarification,
            "clarification_prompt": prompt,
            "topic_shift": topic_shift,
            "ambiguous": ambiguous,
        }

    @staticmethod
    def _is_ambiguous(query: str) -> bool:
        tokens = _tokenize(query)
        return len(tokens) <= 2


@registry.register(
    NodeMetadata(
        name="MemorySummarizerNode",
        description="Persist summarized conversation turns to a memory store.",
        category="conversational_search",
    )
)
class MemorySummarizerNode(TaskNode):
    """Write conversation turns to a :class:`BaseMemoryStore` with retention."""

    memory_store: BaseMemoryStore = Field(
        description="Backing store used to persist conversation turns.",
    )
    session_id_key: str = Field(
        default="session_id", description="Key holding the conversation session id."
    )
    history_key: str = Field(
        default="conversation_history",
        description="Key containing the list of conversation turns to persist.",
    )
    max_turns: int = Field(
        default=50, gt=0, description="Maximum number of turns to retain in memory."
    )
    retention_tokens: int = Field(
        default=400,
        gt=0,
        description="Approximate token budget for returned summaries.",
    )
    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Persist conversation history and return a compact summary."""
        session_id = state.get("inputs", {}).get(self.session_id_key)
        if not isinstance(session_id, str) or not session_id.strip():
            msg = "MemorySummarizerNode requires a non-empty session_id"
            raise ValueError(msg)

        history = state.get("results", {}).get(self.history_key)
        if history is None:
            history = state.get("inputs", {}).get(self.history_key)

        if not isinstance(history, list):
            msg = "conversation_history must be provided as a list"
            raise ValueError(msg)

        turns = [ConversationTurn.model_validate(item) for item in history]
        persisted = 0

        for turn in turns[-self.max_turns :]:
            await self.memory_store.save_turn(
                session_id,
                Turn(
                    session_id=session_id,
                    role=turn.role,
                    content=turn.content,
                    metadata=turn.metadata,
                ),
            )
            persisted += 1

        retained_history = await self.memory_store.get_history(
            session_id, self.max_turns
        )
        summary, truncated = self._summarize(retained_history)

        return {
            "session_id": session_id,
            "summary": summary,
            "persisted_turns": persisted,
            "truncated": truncated,
        }

    def _summarize(self, turns: list[Turn]) -> tuple[str, bool]:
        tokens = 0
        kept: list[Turn] = []
        truncated = False

        for turn in reversed(turns):
            token_count = len(turn.content.split())
            if tokens + token_count > self.retention_tokens:
                truncated = True
                break
            kept.append(turn)
            tokens += token_count

        kept.reverse()
        summary = " | ".join(f"{turn.role}: {turn.content}" for turn in kept)
        return summary, truncated
