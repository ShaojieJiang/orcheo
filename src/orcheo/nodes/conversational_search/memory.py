"""Memory abstractions for conversational search."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, Field


class Turn(BaseModel):
    """Canonical representation of a persisted conversation turn."""

    session_id: str = Field(description="Conversation session identifier")
    role: str = Field(description="Speaker role for this turn")
    content: str = Field(description="Turn payload")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured metadata captured alongside the turn",
    )


class MemorySession(BaseModel):
    """In-memory representation of a conversation session."""

    session_id: str
    turns: list[Turn] = Field(default_factory=list)
    summary: str | None = None


class BaseMemoryStore(ABC):
    """Abstract interface for conversation memory storage backends."""

    @abstractmethod
    async def get_session(self, session_id: str) -> MemorySession:
        """Return the session associated with ``session_id``."""

    @abstractmethod
    async def save_turn(self, session_id: str, turn: Turn) -> None:
        """Persist a turn for the given session."""

    @abstractmethod
    async def get_history(self, session_id: str, limit: int) -> list[Turn]:
        """Return the most recent ``limit`` turns for the session."""

    @abstractmethod
    async def cleanup(self, session_id: str) -> None:
        """Remove all state for ``session_id``."""


class InMemoryMemoryStore(BaseMemoryStore):
    """Simple in-memory memory store for testing and local graphs."""

    def __init__(self, max_turns: int | None = None) -> None:
        """Initialize the store with an optional retention budget."""
        self._sessions: dict[str, MemorySession] = {}
        self._max_turns = max_turns

    async def get_session(self, session_id: str) -> MemorySession:
        """Return the session, initializing it when missing."""
        if session_id not in self._sessions:
            self._sessions[session_id] = MemorySession(session_id=session_id)
        return self._sessions[session_id]

    async def save_turn(self, session_id: str, turn: Turn) -> None:
        """Save a turn and enforce the optional retention limit."""
        session = await self.get_session(session_id)
        session.turns.append(turn)
        if self._max_turns is not None and len(session.turns) > self._max_turns:
            session.turns = session.turns[-self._max_turns :]

    async def get_history(self, session_id: str, limit: int) -> list[Turn]:
        """Return the most recent ``limit`` turns for the session."""
        session = await self.get_session(session_id)
        return session.turns[-limit:]

    async def cleanup(self, session_id: str) -> None:
        """Remove session data entirely."""
        self._sessions.pop(session_id, None)
