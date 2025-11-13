"""Pydantic schemas describing workflow traces."""

from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class TraceTokenUsage(BaseModel):
    """Aggregate token usage captured for a trace."""

    input: int = 0
    output: int = 0


class TraceExecutionMetadata(BaseModel):
    """Metadata describing the traced workflow execution."""

    id: str
    workflow_id: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    trace_id: str | None = None
    token_usage: TraceTokenUsage = Field(default_factory=TraceTokenUsage)


class TraceSpanStatus(BaseModel):
    """Status payload attached to a trace span."""

    code: Literal["OK", "ERROR", "UNSET"]
    message: str | None = None


class TraceSpanEvent(BaseModel):
    """Event captured on a span."""

    name: str
    time: datetime
    attributes: dict[str, Any] = Field(default_factory=dict)


class TraceSpanResponse(BaseModel):
    """Serialized representation of a span in a workflow trace."""

    span_id: str
    parent_span_id: str | None = None
    name: str
    start_time: datetime
    end_time: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[TraceSpanEvent] = Field(default_factory=list)
    links: list[dict[str, Any]] = Field(default_factory=list)
    status: TraceSpanStatus | None = None


class TracePageInfo(BaseModel):
    """Cursor metadata for paginated trace responses."""

    has_next_page: bool = False
    cursor: str | None = None


class ExecutionTraceResponse(BaseModel):
    """Complete trace payload returned by the REST API."""

    execution: TraceExecutionMetadata
    spans: list[TraceSpanResponse] = Field(default_factory=list)
    page_info: TracePageInfo = Field(default_factory=TracePageInfo)


class TraceUpdateMessage(BaseModel):
    """Realtime trace update payload published over WebSocket channels."""

    type: Literal["trace:update"] = "trace:update"
    execution_id: str
    trace_id: str | None = None
    spans: list[TraceSpanResponse] = Field(default_factory=list)
    complete: bool = False
