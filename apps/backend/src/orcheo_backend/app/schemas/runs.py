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


# -- Execution history responses -------------------------------------------


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
    trace_id: str | None = None
    trace_started_at: datetime | None = None
    trace_completed_at: datetime | None = None
    trace_last_span_at: datetime | None = None


class RunReplayRequest(BaseModel):
    """Request body for replaying a run from a given step index."""

    from_step: int = Field(default=0, ge=0)


class CronDispatchRequest(BaseModel):
    """Request body for dispatching cron triggers."""

    now: datetime | None = None


# -- Trace API responses ----------------------------------------------------


class TraceTokenUsage(BaseModel):
    """Aggregate token usage metrics for an execution trace."""

    input: int = 0
    output: int = 0


class TraceSpanEvent(BaseModel):
    """Event captured within a trace span."""

    name: str
    time: datetime
    attributes: dict[str, Any] = Field(default_factory=dict)


class TraceSpanStatus(BaseModel):
    """Status metadata for a trace span."""

    code: str
    message: str | None = None


class TraceSpanResponse(BaseModel):
    """Serialized representation of an individual span."""

    span_id: str
    parent_span_id: str | None = None
    name: str
    start_time: datetime
    end_time: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[TraceSpanEvent] = Field(default_factory=list)
    status: TraceSpanStatus | None = None


class TraceExecutionSummary(BaseModel):
    """High-level metadata describing an execution trace."""

    id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    trace_id: str | None = None
    token_usage: TraceTokenUsage | None = None


class TracePageInfo(BaseModel):
    """Pagination metadata for trace span collections."""

    has_next_page: bool
    cursor: int | None = None


class RunTraceResponse(BaseModel):
    """Trace payload returned by the execution trace endpoint."""

    execution: TraceExecutionSummary
    spans: list[TraceSpanResponse] = Field(default_factory=list)
    page_info: TracePageInfo = Field(
        default_factory=lambda: TracePageInfo(has_next_page=False, cursor=None)
    )


class TraceUpdateMessage(BaseModel):
    """Realtime trace update delivered over websocket channels."""

    type: Literal["trace:update"] = "trace:update"
    execution_id: str
    trace_id: str | None = None
    spans: list[TraceSpanResponse] = Field(default_factory=list)
    complete: bool = False
    cursor: int | None = None
