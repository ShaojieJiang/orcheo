"""Run lifecycle and history schemas."""

from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class RunActionRequest(BaseModel):
    """Base payload for run lifecycle transitions."""

    actor: str


class RunSucceedRequest(RunActionRequest):
    """Payload for marking a run as succeeded."""

    output: dict[str, Any] | None = None


class RunFailRequest(RunActionRequest):
    """Payload for marking a run as failed."""

    error: str


class RunCancelRequest(RunActionRequest):
    """Payload for cancelling a run."""

    reason: str | None = None


class RunHistoryStepResponse(BaseModel):
    """Response payload describing a single run history step."""

    index: int
    at: datetime
    payload: dict[str, Any]


class RunHistoryResponse(BaseModel):
    """Execution history response returned by the API."""

    execution_id: str
    workflow_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    steps: list[RunHistoryStepResponse] = Field(default_factory=list)


class RunReplayRequest(BaseModel):
    """Request body for replaying a run from a given step index."""

    from_step: int = Field(default=0, ge=0)


class CronDispatchRequest(BaseModel):
    """Request body for dispatching cron triggers."""

    now: datetime | None = None


class RunTraceSpanStatus(BaseModel):
    """Status payload describing a span outcome."""

    code: Literal["UNSET", "OK", "ERROR"]
    message: str | None = None


class RunTraceSpanEvent(BaseModel):
    """Event captured within a span."""

    name: str
    time: datetime
    attributes: dict[str, Any] = Field(default_factory=dict)


class RunTraceSpan(BaseModel):
    """Span representation returned by the trace endpoint."""

    span_id: str
    parent_span_id: str | None = None
    name: str
    start_time: datetime
    end_time: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[RunTraceSpanEvent] = Field(default_factory=list)
    status: RunTraceSpanStatus | None = None


class RunTraceExecutionSummary(BaseModel):
    """Execution metadata attached to a trace response."""

    execution_id: str
    workflow_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    trace_id: str | None = None
    token_usage: dict[str, int] | None = None


class RunTracePageInfo(BaseModel):
    """Pagination metadata for trace span payloads."""

    has_next_page: bool = False
    cursor: str | None = None


class RunTraceResponse(BaseModel):
    """Trace payload combining execution metadata and spans."""

    execution: RunTraceExecutionSummary
    spans: list[RunTraceSpan] = Field(default_factory=list)
    page_info: RunTracePageInfo = Field(default_factory=RunTracePageInfo)


class RunTraceUpdateMessage(BaseModel):
    """Realtime update payload broadcast over the execution websocket."""

    type: Literal["trace:update"] = "trace:update"
    execution_id: str
    trace_id: str | None = None
    spans: list[RunTraceSpan] = Field(default_factory=list)
    complete: bool = False
