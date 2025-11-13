from __future__ import annotations
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any
from orcheo.models import CredentialHealthStatus
from orcheo.tracing.workflow import (
    _coalesce_status as _trace_coalesce_status,
)
from orcheo.tracing.workflow import (
    _extract_latency as _trace_extract_latency,
)
from orcheo.tracing.workflow import (
    _extract_token_usage as _trace_extract_token_usage,
)
from orcheo.tracing.workflow import (
    _node_attributes as _trace_node_attributes,
)
from orcheo.tracing.workflow import (
    _preview_text as _trace_preview_text,
)
from orcheo.tracing.workflow import (
    _token_usage_threshold as _trace_token_threshold,
)
from orcheo.vault.oauth import CredentialHealthReport
from orcheo_backend.app.history import RunHistoryRecord, RunHistoryStep
from orcheo_backend.app.schemas.credentials import (
    CredentialHealthItem,
    CredentialHealthResponse,
)
from orcheo_backend.app.schemas.runs import (
    RunHistoryResponse,
    RunHistoryStepResponse,
    RunTraceResponse,
    TraceExecutionSummary,
    TracePageInfo,
    TraceSpanEvent,
    TraceSpanResponse,
    TraceSpanStatus,
    TraceTokenUsage,
    TraceUpdateMessage,
)


_ROOT_SPAN_NAME = "workflow.execution"


def history_to_response(
    record: RunHistoryRecord,
    *,
    from_step: int = 0,
) -> RunHistoryResponse:
    """Convert a history record into a serialisable response."""
    steps = [
        RunHistoryStepResponse(
            index=step.index,
            at=step.at,
            payload=step.payload,
        )
        for step in record.steps[from_step:]
    ]
    return RunHistoryResponse(
        execution_id=record.execution_id,
        workflow_id=record.workflow_id,
        status=record.status,
        started_at=record.started_at,
        completed_at=record.completed_at,
        error=record.error,
        inputs=record.inputs,
        steps=steps,
        trace_id=record.trace_id,
        trace_started_at=record.trace_started_at,
        trace_completed_at=record.trace_completed_at,
        trace_last_span_at=record.trace_last_span_at,
    )


def trace_to_response(
    record: RunHistoryRecord,
    *,
    cursor: int = 0,
    limit: int | None = None,
) -> RunTraceResponse:
    """Serialize a stored history record into an API-ready trace response."""
    start_index = max(cursor, 0)
    remaining_steps = record.steps[start_index:]
    if limit is not None:
        remaining_steps = remaining_steps[:limit]

    spans: list[TraceSpanResponse] = []
    if start_index == 0:
        spans.append(
            _build_root_span(
                execution_id=record.execution_id,
                workflow_id=record.workflow_id,
                trace_id=record.trace_id,
                started_at=record.trace_started_at or record.started_at,
                completed_at=record.trace_completed_at or record.completed_at,
                status=record.status,
                error=record.error,
            )
        )
    for step in remaining_steps:
        spans.extend(_build_node_spans(record.execution_id, step))

    processed_count = len(remaining_steps)
    next_cursor = start_index + processed_count
    has_next = next_cursor < len(record.steps)
    aggregate_usage = _aggregate_token_usage(record.steps)
    usage_summary: TraceTokenUsage | None = None
    if aggregate_usage.input or aggregate_usage.output:
        usage_summary = aggregate_usage

    summary = TraceExecutionSummary(
        id=record.execution_id,
        status=record.status,
        started_at=record.trace_started_at or record.started_at,
        finished_at=record.trace_completed_at or record.completed_at,
        trace_id=record.trace_id,
        token_usage=usage_summary,
    )

    page_info = TracePageInfo(has_next_page=has_next, cursor=next_cursor)
    return RunTraceResponse(execution=summary, spans=spans, page_info=page_info)


def trace_update_message(
    *,
    execution_id: str,
    workflow_id: str,
    trace_id: str | None,
    trace_started_at: datetime,
    steps: Sequence[RunHistoryStep] = (),
    include_root: bool = False,
    status: str = "running",
    error: str | None = None,
    complete: bool = False,
    completed_at: datetime | None = None,
    cursor: int | None = None,
) -> TraceUpdateMessage | None:
    """Build a websocket payload representing incremental span updates."""
    spans: list[TraceSpanResponse] = []
    if include_root:
        spans.append(
            _build_root_span(
                execution_id=execution_id,
                workflow_id=workflow_id,
                trace_id=trace_id,
                started_at=trace_started_at,
                completed_at=completed_at,
                status=status,
                error=error,
            )
        )

    for step in steps:
        spans.extend(_build_node_spans(execution_id, step))

    if not spans and not complete:
        return None

    cursor_value = cursor
    if cursor_value is None:
        if steps:
            cursor_value = steps[-1].index + 1
        elif complete:
            cursor_value = len(steps)
        else:
            cursor_value = 0

    return TraceUpdateMessage(
        execution_id=execution_id,
        trace_id=trace_id,
        spans=spans,
        complete=complete,
        cursor=cursor_value,
    )


def trace_completion_message(record: RunHistoryRecord) -> TraceUpdateMessage | None:
    """Return a websocket payload describing the final trace state."""
    return trace_update_message(
        execution_id=record.execution_id,
        workflow_id=record.workflow_id,
        trace_id=record.trace_id,
        trace_started_at=record.trace_started_at or record.started_at,
        steps=(),
        include_root=True,
        status=record.status,
        error=record.error,
        complete=True,
        completed_at=record.trace_completed_at or record.completed_at,
        cursor=len(record.steps),
    )


def health_report_to_response(
    report: CredentialHealthReport,
) -> CredentialHealthResponse:
    """Convert a credential health report into a response payload."""
    credentials = [
        CredentialHealthItem(
            credential_id=str(result.credential_id),
            name=result.name,
            provider=result.provider,
            status=result.status,
            last_checked_at=result.last_checked_at,
            failure_reason=result.failure_reason,
        )
        for result in report.results
    ]
    overall_status = (
        CredentialHealthStatus.HEALTHY
        if report.is_healthy
        else CredentialHealthStatus.UNHEALTHY
    )
    return CredentialHealthResponse(
        workflow_id=str(report.workflow_id),
        status=overall_status,
        checked_at=report.checked_at,
        credentials=credentials,
    )


def _build_root_span(
    *,
    execution_id: str,
    workflow_id: str,
    trace_id: str | None,
    started_at: datetime,
    completed_at: datetime | None,
    status: str,
    error: str | None,
) -> TraceSpanResponse:
    attributes = {
        "orcheo.execution.id": execution_id,
        "orcheo.workflow.id": workflow_id,
    }
    return TraceSpanResponse(
        span_id=_root_span_id(execution_id),
        parent_span_id=None,
        name=_ROOT_SPAN_NAME,
        start_time=started_at,
        end_time=completed_at,
        attributes=attributes,
        events=[],
        status=_status_from_text(status, error),
    )


def _build_node_spans(
    execution_id: str,
    step: RunHistoryStep,
) -> list[TraceSpanResponse]:
    spans: list[TraceSpanResponse] = []
    for node_name, payload in step.payload.items():
        if not isinstance(payload, Mapping):
            continue
        attributes = dict(_trace_node_attributes(node_name, payload))
        input_tokens, output_tokens = _trace_extract_token_usage(payload)
        if input_tokens is not None:
            attributes["orcheo.token.input"] = input_tokens
        if output_tokens is not None:
            attributes["orcheo.token.output"] = output_tokens
        artifacts = _extract_artifact_ids(payload)
        if artifacts:
            attributes["orcheo.artifact.ids"] = artifacts
        events = _build_span_events(payload, step.at, input_tokens, output_tokens)
        status = _node_status(payload)
        duration_ms = _trace_extract_latency(payload)
        end_time = _resolve_end_time(step.at, duration_ms)
        span_name = str(attributes.get("orcheo.node.display_name", node_name))
        spans.append(
            TraceSpanResponse(
                span_id=_node_span_id(execution_id, step.index, node_name),
                parent_span_id=_root_span_id(execution_id),
                name=span_name,
                start_time=step.at,
                end_time=end_time,
                attributes=attributes,
                events=events,
                status=status,
            )
        )
    return spans


def _aggregate_token_usage(steps: Sequence[RunHistoryStep]) -> TraceTokenUsage:
    total_input = 0
    total_output = 0
    for step in steps:
        for payload in step.payload.values():
            if not isinstance(payload, Mapping):
                continue
            input_tokens, output_tokens = _trace_extract_token_usage(payload)
            if input_tokens:
                total_input += input_tokens
            if output_tokens:
                total_output += output_tokens
    return TraceTokenUsage(input=total_input, output=total_output)


def _build_span_events(
    payload: Mapping[str, Any],
    event_time: datetime,
    input_tokens: int | None,
    output_tokens: int | None,
) -> list[TraceSpanEvent]:
    events: list[TraceSpanEvent] = []
    events.extend(
        _collect_named_text_events(payload, ("prompts", "prompt"), "prompt", event_time)
    )
    events.extend(
        _collect_named_text_events(
            payload, ("responses", "response"), "response", event_time
        )
    )
    events.extend(_collect_message_events(payload, event_time))
    error_event = _collect_error_event(payload, event_time)
    if error_event is not None:
        events.append(error_event)
    token_event = _collect_token_event(input_tokens, output_tokens, event_time)
    if token_event is not None:
        events.append(token_event)
    return events


def _collect_named_text_events(
    payload: Mapping[str, Any],
    keys: Sequence[str],
    event_name: str,
    event_time: datetime,
) -> list[TraceSpanEvent]:
    events: list[TraceSpanEvent] = []
    for key in keys:
        if key in payload:
            events.extend(_text_events(event_name, payload[key], event_time))
    return events


def _collect_message_events(
    payload: Mapping[str, Any],
    event_time: datetime,
) -> list[TraceSpanEvent]:
    messages = payload.get("messages")
    if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)):
        return []
    events: list[TraceSpanEvent] = []
    for message in messages:
        if isinstance(message, Mapping):
            role = str(message.get("role", "unknown"))
            content = message.get("content")
        else:
            role = "message"
            content = message
        events.append(
            TraceSpanEvent(
                name="message",
                time=event_time,
                attributes={
                    "role": role,
                    "preview": _trace_preview_text(content),
                },
            )
        )
    return events


def _collect_error_event(
    payload: Mapping[str, Any],
    event_time: datetime,
) -> TraceSpanEvent | None:
    error_message = _extract_error_message(payload)
    if not error_message:
        return None
    return TraceSpanEvent(
        name="error.detail",
        time=event_time,
        attributes={"message": _trace_preview_text(error_message)},
    )


def _collect_token_event(
    input_tokens: int | None,
    output_tokens: int | None,
    event_time: datetime,
) -> TraceSpanEvent | None:
    threshold = _trace_token_threshold()
    if (input_tokens or 0) <= threshold and (output_tokens or 0) <= threshold:
        return None
    return TraceSpanEvent(
        name="token.chunk",
        time=event_time,
        attributes={
            "input": input_tokens or 0,
            "output": output_tokens or 0,
            "reason": "high_usage",
        },
    )


def _text_events(
    event_name: str,
    value: Any,
    event_time: datetime,
) -> list[TraceSpanEvent]:
    events: list[TraceSpanEvent] = []
    if isinstance(value, Mapping):
        events.append(
            TraceSpanEvent(
                name=event_name,
                time=event_time,
                attributes={k: _trace_preview_text(v) for k, v in value.items()},
            )
        )
        return events
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            events.append(
                TraceSpanEvent(
                    name=event_name,
                    time=event_time,
                    attributes={"preview": _trace_preview_text(item)},
                )
            )
        return events
    events.append(
        TraceSpanEvent(
            name=event_name,
            time=event_time,
            attributes={"preview": _trace_preview_text(value)},
        )
    )
    return events


def _node_status(payload: Mapping[str, Any]) -> TraceSpanStatus | None:
    status = _trace_coalesce_status(payload)
    if status is None:
        return TraceSpanStatus(code="UNSET")
    if status == "error":
        return TraceSpanStatus(
            code="ERROR",
            message=_extract_error_message(payload),
        )
    if status in {"success", "succeeded", "completed"}:
        return TraceSpanStatus(code="OK")
    if status in {"cancelled", "canceled"}:
        return TraceSpanStatus(code="ERROR", message="cancelled")
    return TraceSpanStatus(code=status.upper())


def _status_from_text(status: str, error: str | None) -> TraceSpanStatus:
    normalized = (status or "").lower()
    if normalized in {"completed", "succeeded", "success"}:
        return TraceSpanStatus(code="OK")
    if normalized in {"failed", "error"}:
        return TraceSpanStatus(code="ERROR", message=error)
    if normalized in {"cancelled", "canceled"}:
        return TraceSpanStatus(code="ERROR", message=error or "cancelled")
    if normalized == "running":
        return TraceSpanStatus(code="UNSET")
    if normalized:
        return TraceSpanStatus(code=normalized.upper(), message=error)
    return TraceSpanStatus(code="UNSET", message=error)


def _extract_artifact_ids(payload: Mapping[str, Any]) -> list[str]:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, Sequence) or isinstance(artifacts, (str, bytes)):
        return []
    result: list[str] = []
    for artifact in artifacts:
        if isinstance(artifact, Mapping) and artifact.get("id") is not None:
            result.append(str(artifact["id"]))
        else:
            result.append(str(artifact))
    return result


def _extract_error_message(payload: Mapping[str, Any]) -> str | None:
    error_obj = payload.get("error")
    if isinstance(error_obj, Mapping):
        message = error_obj.get("message")
        if message is not None:
            return str(message)
    elif isinstance(error_obj, str):
        return error_obj
    return None


def _resolve_end_time(start: datetime, duration_ms: int | None) -> datetime:
    if duration_ms is None:
        return start
    try:
        return start + timedelta(milliseconds=int(duration_ms))
    except (TypeError, ValueError, OverflowError):
        return start


def _root_span_id(execution_id: str) -> str:
    return f"{execution_id}:root"


def _node_span_id(execution_id: str, step_index: int, node_name: str) -> str:
    return f"{execution_id}:{step_index}:{node_name}"


__all__ = [
    "health_report_to_response",
    "history_to_response",
    "trace_completion_message",
    "trace_to_response",
    "trace_update_message",
]
