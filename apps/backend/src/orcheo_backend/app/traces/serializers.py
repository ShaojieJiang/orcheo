"""Utilities for serialising workflow traces from history records."""

from __future__ import annotations
import hashlib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
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
    _preview_text as _trace_preview_text,
)
from orcheo_backend.app.history import RunHistoryRecord, RunHistoryStep
from orcheo_backend.app.schemas.traces import (
    ExecutionTraceResponse,
    TraceExecutionMetadata,
    TracePageInfo,
    TraceSpanEvent,
    TraceSpanResponse,
    TraceSpanStatus,
    TraceTokenUsage,
    TraceUpdateMessage,
)


_ROOT_SPAN_NAME = "workflow.execution"
_TERMINAL_STATUSES = {
    "completed",
    "success",
    "succeeded",
    "cancelled",
    "canceled",
    "error",
    "failed",
    "failure",
}


def build_execution_trace(record: RunHistoryRecord) -> ExecutionTraceResponse:
    """Construct a serialised trace payload for the provided history record."""
    root_span = _build_root_span(
        execution_id=record.execution_id,
        workflow_id=record.workflow_id,
        inputs=record.inputs,
        trace_started_at=record.trace_started_at or record.started_at,
        finished_at=_resolve_trace_finished_at(record),
        status=record.status,
        error_message=record.error,
    )

    spans: list[TraceSpanResponse] = [root_span]
    total_input = 0
    total_output = 0

    for step in record.steps:
        child_spans, usage = _build_spans_for_step(
            execution_id=record.execution_id,
            step=step,
            default_parent=root_span.span_id,
        )
        spans.extend(child_spans)
        total_input += usage.input
        total_output += usage.output

    spans.sort(key=lambda span: (span.start_time, span.span_id))
    token_usage = TraceTokenUsage(input=total_input, output=total_output)

    metadata = TraceExecutionMetadata(
        id=record.execution_id,
        workflow_id=record.workflow_id,
        status=record.status,
        started_at=record.trace_started_at or record.started_at,
        finished_at=_resolve_trace_finished_at(record),
        trace_id=record.trace_id,
        token_usage=token_usage,
    )

    return ExecutionTraceResponse(
        execution=metadata,
        spans=spans,
        page_info=TracePageInfo(has_next_page=False, cursor=None),
    )


def build_trace_update_message(
    *,
    workflow_id: str,
    execution_id: str,
    trace_id: str | None,
    trace_started_at: datetime | None,
    inputs: Mapping[str, Any] | None,
    step: RunHistoryStep,
) -> TraceUpdateMessage | None:
    """Build a websocket update payload for the provided step."""
    parent_span_id = _root_span_id(execution_id)
    spans, _ = _build_spans_for_step(
        execution_id=execution_id,
        step=step,
        default_parent=parent_span_id,
    )

    complete = _is_terminal_step(step.payload)
    if complete:
        root_span = _build_root_span(
            execution_id=execution_id,
            workflow_id=workflow_id,
            inputs=inputs or {},
            trace_started_at=trace_started_at,
            finished_at=step.at,
            status=_extract_status_from_payload(step.payload) or "running",
            error_message=_extract_error_message(step.payload),
        )
        spans.append(root_span)

    if not spans and not complete:
        return None

    return TraceUpdateMessage(
        execution_id=execution_id,
        trace_id=trace_id,
        spans=spans,
        complete=complete,
    )


def _build_spans_for_step(
    *,
    execution_id: str,
    step: RunHistoryStep,
    default_parent: str,
) -> tuple[list[TraceSpanResponse], TraceTokenUsage]:
    payload = step.payload
    if not isinstance(payload, Mapping):
        return [], TraceTokenUsage()

    spans: list[TraceSpanResponse] = []
    total_input = 0
    total_output = 0

    for node_name, node_payload in payload.items():
        if not isinstance(node_payload, Mapping):
            continue
        span_id = _child_span_id(execution_id, step.index, node_name)
        attributes = _node_attributes(node_name, node_payload)
        events = _collect_events(node_payload, step.at)
        status = _span_status(node_payload)
        start_time = step.at
        latency_ms = _trace_extract_latency(node_payload)
        end_time = (
            start_time + timedelta(milliseconds=latency_ms)
            if latency_ms is not None
            else None
        )

        spans.append(
            TraceSpanResponse(
                span_id=span_id,
                parent_span_id=default_parent,
                name=str(attributes.get("orcheo.node.display_name", node_name)),
                start_time=start_time,
                end_time=end_time,
                attributes=attributes,
                events=events,
                status=status,
            )
        )

        usage = _trace_extract_token_usage(node_payload)
        if usage[0] is not None:
            total_input += usage[0]
        if usage[1] is not None:
            total_output += usage[1]

    spans.sort(key=lambda span: (span.start_time, span.span_id))
    return spans, TraceTokenUsage(input=total_input, output=total_output)


def _build_root_span(
    *,
    execution_id: str,
    workflow_id: str,
    inputs: Mapping[str, Any] | None,
    trace_started_at: datetime | None,
    finished_at: datetime | None,
    status: str,
    error_message: str | None,
) -> TraceSpanResponse:
    started_at = trace_started_at or datetime.now(tz=UTC)
    attributes: dict[str, Any] = {
        "orcheo.execution.id": execution_id,
        "orcheo.workflow.id": workflow_id,
    }
    if inputs:
        keys = sorted(inputs.keys())
        attributes["orcheo.execution.input_keys"] = keys
        attributes["orcheo.execution.input_count"] = len(keys)

    span_status = _status_from_string(status, error_message)

    return TraceSpanResponse(
        span_id=_root_span_id(execution_id),
        parent_span_id=None,
        name=_ROOT_SPAN_NAME,
        start_time=started_at,
        end_time=finished_at,
        attributes=attributes,
        events=[],
        status=span_status,
    )


def _node_attributes(node_name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    display_name = str(payload.get("display_name", node_name))
    attributes: dict[str, Any] = {
        "orcheo.node.id": str(payload.get("id", node_name)),
        "orcheo.node.display_name": display_name,
    }
    kind = payload.get("kind") or payload.get("type")
    if kind is not None:
        attributes["orcheo.node.kind"] = str(kind)
    status = _trace_coalesce_status(payload)
    if status:
        attributes["orcheo.node.status"] = status
    latency = _trace_extract_latency(payload)
    if latency is not None:
        attributes["orcheo.node.latency_ms"] = latency

    usage = _trace_extract_token_usage(payload)
    if usage[0] is not None:
        attributes["orcheo.token.input"] = usage[0]
    if usage[1] is not None:
        attributes["orcheo.token.output"] = usage[1]

    artifacts = payload.get("artifacts")
    if isinstance(artifacts, Sequence) and artifacts:
        attributes["orcheo.artifact.ids"] = [
            _coerce_artifact_id(artifact) for artifact in artifacts
        ]

    error_obj = payload.get("error")
    if isinstance(error_obj, Mapping):
        error_code = error_obj.get("code")
        if error_code is not None:
            attributes["orcheo.error.code"] = str(error_code)

    return attributes


def _collect_events(payload: Mapping[str, Any], at: datetime) -> list[TraceSpanEvent]:
    events: list[TraceSpanEvent] = []

    for key in ("prompts", "prompt"):
        if key in payload:
            events.extend(_text_events("prompt", payload[key], at))
    for key in ("responses", "response"):
        if key in payload:
            events.extend(_text_events("response", payload[key], at))

    messages = payload.get("messages")
    if isinstance(messages, Sequence) and not isinstance(messages, (str, bytes)):
        for message in messages:
            if isinstance(message, Mapping):
                attributes = {
                    "role": str(message.get("role", "message")),
                    "preview": _trace_preview_text(message.get("content")),
                }
            else:
                attributes = {
                    "role": "message",
                    "preview": _trace_preview_text(message),
                }
            events.append(
                TraceSpanEvent(
                    name="message",
                    time=at,
                    attributes=attributes,
                )
            )

    return events


def _text_events(name: str, value: Any, at: datetime) -> list[TraceSpanEvent]:
    if isinstance(value, Mapping):
        attributes = {k: _trace_preview_text(v) for k, v in value.items()}
        return [TraceSpanEvent(name=name, time=at, attributes=attributes)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [
            TraceSpanEvent(
                name=name,
                time=at,
                attributes={"preview": _trace_preview_text(item)},
            )
            for item in value
        ]
    return [
        TraceSpanEvent(
            name=name,
            time=at,
            attributes={"preview": _trace_preview_text(value)},
        )
    ]


def _span_status(payload: Mapping[str, Any]) -> TraceSpanStatus | None:
    status = _trace_coalesce_status(payload)
    if not status:
        return None
    status_lower = status.lower()
    if status_lower in {"error", "failed", "failure"}:
        message = _extract_error_message(payload)
        return TraceSpanStatus(code="ERROR", message=message)
    if status_lower in {"completed", "success", "succeeded"}:
        return TraceSpanStatus(code="OK", message=None)
    if status_lower in {"cancelled", "canceled"}:
        reason = payload.get("reason")
        message = str(reason) if isinstance(reason, (str, bytes)) else None
        return TraceSpanStatus(code="ERROR", message=message)
    return TraceSpanStatus(code="UNSET", message=None)


def _status_from_string(status: str, error_message: str | None) -> TraceSpanStatus:
    status_lower = status.lower()
    if status_lower in {"completed", "success", "succeeded"}:
        return TraceSpanStatus(code="OK", message=None)
    if status_lower in {"cancelled", "canceled"}:
        return TraceSpanStatus(code="ERROR", message=error_message)
    if status_lower in {"error", "failed", "failure"}:
        return TraceSpanStatus(code="ERROR", message=error_message)
    return TraceSpanStatus(code="UNSET", message=error_message)


def _extract_status_from_payload(payload: Mapping[str, Any]) -> str | None:
    for key in ("status", "state", "result"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return None


def _extract_error_message(payload: Mapping[str, Any]) -> str | None:
    error_obj = payload.get("error")
    if isinstance(error_obj, Mapping):
        for key in ("message", "detail", "reason"):
            value = error_obj.get(key)
            if isinstance(value, str) and value:
                return value
    if isinstance(error_obj, str) and error_obj:
        return error_obj
    reason = payload.get("reason")
    if isinstance(reason, str) and reason:
        return reason
    return None


def _coerce_artifact_id(value: Any) -> str:
    if isinstance(value, Mapping) and value.get("id") is not None:
        return str(value.get("id"))
    return str(value)


def _root_span_id(execution_id: str) -> str:
    return hashlib.sha1(f"{execution_id}:root".encode()).hexdigest()


def _child_span_id(execution_id: str, step_index: int, node_name: str) -> str:
    raw = f"{execution_id}:{step_index}:{node_name}"
    return hashlib.sha1(raw.encode()).hexdigest()


def _is_terminal_step(payload: Mapping[str, Any] | Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    status = _extract_status_from_payload(payload)
    return bool(status and status.lower() in _TERMINAL_STATUSES)


def _resolve_trace_finished_at(record: RunHistoryRecord) -> datetime | None:
    return record.trace_completed_at or record.trace_last_span_at or record.completed_at


__all__ = [
    "build_execution_trace",
    "build_trace_update_message",
]
