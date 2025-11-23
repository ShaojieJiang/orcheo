"""Data models for conversational search ingestion primitives."""

from __future__ import annotations
from typing import Any
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


class EvaluationExample(BaseModel):
    """Ground truth example used for evaluation workflows."""

    id: str = Field(description="Stable identifier for the evaluation example")
    query: str = Field(min_length=1, description="User query used for retrieval")
    relevant_ids: list[str] = Field(
        default_factory=list,
        description="List of chunk or document identifiers considered relevant",
    )
    reference_answer: str | None = Field(
        default=None, description="Optional gold answer for quality evaluation"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary metadata for the example"
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_relevant(self) -> EvaluationExample:
        if any(not item for item in self.relevant_ids):
            msg = "relevant_ids must not contain empty identifiers"
            raise ValueError(msg)
        return self


class FeedbackRecord(BaseModel):
    """User feedback captured for evaluation and analytics."""

    rating: int = Field(ge=1, le=5, description="Discrete satisfaction rating")
    comment: str | None = Field(
        default=None, description="Optional free-form feedback text"
    )
    user_id: str | None = Field(
        default=None, description="Optional identifier for the submitting user"
    )
    tags: list[str] = Field(
        default_factory=list, description="Normalized tags describing the feedback"
    )
    timestamp: float | None = Field(
        default=None, description="Optional epoch timestamp when feedback was given"
    )

    model_config = ConfigDict(extra="forbid")


class ComplianceFinding(BaseModel):
    """Finding generated during compliance or privacy checks."""

    policy: str = Field(description="Name of the policy evaluated")
    message: str = Field(description="Human readable description of the finding")
    severity: str = Field(
        default="warning",
        description="Severity level such as info, warning, or critical",
    )

    model_config = ConfigDict(extra="forbid")
