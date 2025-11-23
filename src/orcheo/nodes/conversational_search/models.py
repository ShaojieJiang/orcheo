"""Data models for conversational search ingestion primitives."""

from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class Document(BaseModel):
    """Normalized document representation for ingestion."""

    id: str = Field(description="Stable identifier for the document")
    content: str = Field(min_length=1, description="Raw document text content")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary metadata"
    )
    source: str | None = Field(
        default=None,
        description=(
            "Optional human-readable source for traceability (e.g., URL, filename)"
        ),
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _normalize_content(self) -> Document:
        self.content = self.content.strip()
        if not self.content:
            msg = "Document content cannot be empty after trimming whitespace"
            raise ValueError(msg)
        return self


class DocumentChunk(BaseModel):
    """Chunked segment derived from a :class:`Document`."""

    id: str = Field(description="Chunk identifier scoped globally for indexing")
    document_id: str = Field(description="Identifier of the source document")
    index: int = Field(ge=0, description="Chunk index within the source document")
    content: str = Field(min_length=1, description="Text contained in the chunk")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata merged from document and chunk details",
    )

    model_config = ConfigDict(extra="forbid")

    @computed_field  # type: ignore[misc]
    @property
    def token_count(self) -> int:
        """Approximate token count using a whitespace heuristic."""
        return len(self.content.split())

    @model_validator(mode="after")
    def _validate_content(self) -> DocumentChunk:
        self.content = self.content.strip()
        if not self.content:
            msg = "Chunk content cannot be empty after trimming whitespace"
            raise ValueError(msg)
        return self


class VectorRecord(BaseModel):
    """Payload stored in a vector database."""

    id: str = Field(description="Unique identifier for the record")
    values: list[float] = Field(description="Embedding vector values")
    text: str = Field(description="Raw text that generated the embedding")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata persisted alongside the vector"
    )

    model_config = ConfigDict(extra="forbid")


class SearchResult(BaseModel):
    """Normalized retrieval result emitted by search nodes."""

    id: str = Field(description="Identifier of the matching record")
    score: float = Field(description="Relevance score (higher is better)")
    text: str = Field(description="Content associated with the record")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata returned by the retriever"
    )
    source: str | None = Field(
        default=None, description="Origin retriever name (e.g., 'vector', 'bm25')"
    )
    sources: list[str] = Field(
        default_factory=list,
        description="List of retrievers contributing to this result",
    )

    model_config = ConfigDict(extra="forbid")


class ConversationTurn(BaseModel):
    """Single conversation turn with role and content."""

    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, description="Message content for the turn")
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _normalize_content(self) -> ConversationTurn:
        self.content = self.content.strip()
        if not self.content:
            msg = "Conversation turn content cannot be empty"
            raise ValueError(msg)
        return self


class ConversationSession(BaseModel):
    """Conversation session containing history and metadata."""

    session_id: str
    history: list[ConversationTurn] = Field(default_factory=list)
    summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    def append_turn(self, turn: ConversationTurn) -> None:
        """Append ``turn`` to the session history."""
        self.history.append(turn)

    def trim_history(self, max_turns: int) -> None:
        """Trim history to the most recent ``max_turns`` entries."""
        if max_turns <= 0:
            return
        if len(self.history) > max_turns:
            self.history = self.history[-max_turns:]


class MemorySummary(BaseModel):
    """Persisted episodic summary for a conversation session."""

    session_id: str
    summary: str = Field(min_length=1, description="Persisted summary text")
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(extra="forbid")
