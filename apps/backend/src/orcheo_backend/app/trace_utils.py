"""Helpers for assembling workflow trace payloads."""

from __future__ import annotations
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from hashlib import blake2b
from typing import Any
from orcheo.tracing import workflow as tracing_workflow
from orcheo_backend.app.history import RunHistoryRecord, RunHistoryStep
from orcheo_backend.app.schemas.traces import (
    TraceExecutionMetadata,
    TracePageInfo,
    TraceResponse,
    TraceSpanEvent,
    TraceSpanResponse,
    TraceSpanStatus,
    TraceTokenUsage,
    TraceUpdateMessage,
)


def build_trace_response(record: RunHistoryRecord) -> TraceResponse:
    """Convert a history record into a trace response."""
    root_span_id = _derive_root_span_id(record.trace_id, record.execution_id)
    root_span = _build_root_span(record, root_span_id)
    spans: list[TraceSpanResponse] = [root_span]

    total_input = 0
    total_output = 0
    for step in record.steps:
        node_spans = _build_spans_for_step(record, step, root_span_id)
        spans.extend(node_spans)
        for span in node_spans:
            total_input += int(span.attributes.get("orcheo.token.input", 0))
            total_output += int(span.attributes.get("orcheo.token.output", 0))

    execution_metadata = TraceExecutionMetadata(
        id=record.execution_id,
        status=record.status,
        started_at=record.trace_started_at or record.started_at,
        finished_at=record.trace_completed_at or record.completed_at,
        trace_id=record.trace_id,
        token_usage=TraceTokenUsage(input=total_input, output=total_output),
    )

    return TraceResponse(
        execution=execution_metadata,
        spans=spans,
        page_info=TracePageInfo(has_next_page=False, cursor=None),
    )


def build_trace_update(
    record: RunHistoryRecord,
    *,
    step: RunHistoryStep | None = None,
    include_root: bool = False,
    complete: bool = False,
) -> TraceUpdateMessage | None:
    """Assemble a websocket trace update message."""
    root_span_id = _derive_root_span_id(record.trace_id, record.execution_id)
    spans: list[TraceSpanResponse] = []
    if include_root:
        spans.append(_build_root_span(record, root_span_id))
    if step is not None:
        spans.extend(_build_spans_for_step(record, step, root_span_id))

    if not spans and not complete:
        return None

    trace_identifier = record.trace_id or root_span_id
    return TraceUpdateMessage(
        execution_id=record.execution_id,
        trace_id=trace_identifier,
        spans=spans,
        complete=complete,
    )


def _derive_root_span_id(trace_id: str | None, execution_id: str) -> str:
    if trace_id:
        sanitized = trace_id.replace("-", "")
        if len(sanitized) >= 16:
            return sanitized[:16]
    digest = blake2b(f"{execution_id}:root".encode(), digest_size=8)
    return digest.hexdigest()


def _derive_child_span_id(execution_id: str, step_index: int, node_key: str) -> str:
    digest = blake2b(f"{execution_id}:{step_index}:{node_key}".encode(), digest_size=8)
    return digest.hexdigest()


def _build_root_span(record: RunHistoryRecord, span_id: str) -> TraceSpanResponse:
    status = _status_from_history(record)
    attributes = {
        "orcheo.execution.id": record.execution_id,
        "orcheo.workflow.id": record.workflow_id,
    }
    return TraceSpanResponse(
        span_id=span_id,
        parent_span_id=None,
        name="workflow.execution",
        start_time=record.trace_started_at or record.started_at,
        end_time=record.trace_completed_at or record.completed_at,
        attributes=attributes,
        status=status,
    )


def _build_spans_for_step(
    record: RunHistoryRecord,
    step: RunHistoryStep,
    root_span_id: str,
) -> list[TraceSpanResponse]:
    spans: list[TraceSpanResponse] = []
    for node_key, payload in step.payload.items():
        if not isinstance(payload, Mapping):
            continue
        span = _build_node_span(record, step, node_key, payload, root_span_id)
        if span is not None:
            spans.append(span)
    return spans


def _build_node_span(
    record: RunHistoryRecord,
    step: RunHistoryStep,
    node_key: str,
    payload: Mapping[str, Any],
    parent_id: str,
) -> TraceSpanResponse | None:
    attributes = _node_attributes(node_key, payload)
    span_id = _derive_child_span_id(record.execution_id, step.index, node_key)
    name = attributes.get("orcheo.node.display_name", node_key)
    start_time = step.at
    end_time = _compute_end_time(start_time, payload)
    token_input, token_output = _extract_token_usage(payload)
    if token_input is not None:
        attributes["orcheo.token.input"] = token_input
    if token_output is not None:
        attributes["orcheo.token.output"] = token_output
    artifact_ids = _extract_artifact_ids(payload)
    if artifact_ids:
        attributes["orcheo.artifact.ids"] = artifact_ids
    events = list(_collect_message_events(payload, start_time))
    status = _status_from_payload(payload)
    return TraceSpanResponse(
        span_id=span_id,
        parent_span_id=parent_id,
        name=str(name),
        start_time=start_time,
        end_time=end_time,
        attributes=attributes,
        events=events,
        status=status,
    )


def _compute_end_time(
    start_time: datetime, payload: Mapping[str, Any]
) -> datetime | None:
    latency = _extract_latency(payload)
    if latency is None:
        return None
    return start_time + timedelta(milliseconds=latency)


def _node_attributes(node_key: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    display_name = payload.get("display_name") or payload.get("name") or node_key
    attributes: dict[str, Any] = {
        "orcheo.node.id": str(payload.get("id", node_key)),
        "orcheo.node.display_name": str(display_name),
    }
    kind = payload.get("kind") or payload.get("type")
    if kind is not None:
        attributes["orcheo.node.kind"] = str(kind)
    status = _coalesce_status(payload)
    if status:
        attributes["orcheo.node.status"] = status
    latency = _extract_latency(payload)
    if latency is not None:
        attributes["orcheo.node.latency_ms"] = latency
    return attributes


def _extract_artifact_ids(payload: Mapping[str, Any]) -> list[str]:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, Sequence):
        return []
    identifiers: list[str] = []
    for artifact in artifacts:
        if isinstance(artifact, Mapping) and artifact.get("id") is not None:
            identifiers.append(str(artifact.get("id")))
        else:
            identifiers.append(str(artifact))
    return identifiers


def _collect_message_events(
    payload: Mapping[str, Any],
    default_time: datetime,
) -> Sequence[TraceSpanEvent]:
    events: list[TraceSpanEvent] = []
    for key in ("prompts", "prompt"):
        if key in payload:
            events.extend(_build_text_events("prompt", payload[key], default_time))
    for key in ("responses", "response"):
        if key in payload:
            events.extend(_build_text_events("response", payload[key], default_time))
    messages = payload.get("messages")
    if isinstance(messages, Sequence) and not isinstance(messages, (str, bytes)):
        for message in messages:
            if isinstance(message, Mapping):
                role = str(message.get("role", "message"))
                preview = _preview_text(message.get("content"))
            else:
                role = "message"
                preview = _preview_text(message)
            events.append(
                TraceSpanEvent(
                    name="message",
                    time=default_time,
                    attributes={"role": role, "preview": preview},
                )
            )
    return events


def _build_text_events(
    name: str,
    value: Any,
    default_time: datetime,
) -> list[TraceSpanEvent]:
    if isinstance(value, Mapping):
        return [
            TraceSpanEvent(
                name=name,
                time=default_time,
                attributes={key: _preview_text(val) for key, val in value.items()},
            )
        ]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [
            TraceSpanEvent(
                name=name,
                time=default_time,
                attributes={"preview": _preview_text(item)},
            )
            for item in value
        ]
    return [
        TraceSpanEvent(
            name=name,
            time=default_time,
            attributes={"preview": _preview_text(value)},
        )
    ]


def _status_from_history(record: RunHistoryRecord) -> TraceSpanStatus:
    status = record.status.lower()
    if status in {"completed", "success", "succeeded"}:
        return TraceSpanStatus(code="OK")
    if status in {"error", "failed"}:
        return TraceSpanStatus(code="ERROR", message=record.error)
    if status in {"cancelled", "canceled"}:
        return TraceSpanStatus(code="ERROR", message=record.error or "cancelled")
    return TraceSpanStatus(code="UNSET")


def _status_from_payload(payload: Mapping[str, Any]) -> TraceSpanStatus:
    status = _coalesce_status(payload)
    if not status:
        return TraceSpanStatus(code="UNSET")
    lowered = status.lower()
    if lowered in {"completed", "success", "succeeded"}:
        return TraceSpanStatus(code="OK")
    if lowered in {"error", "failed"}:
        message = _extract_error_message(payload)
        return TraceSpanStatus(code="ERROR", message=message)
    if lowered in {"cancelled", "canceled"}:
        reason = payload.get("reason") or payload.get("error") or "cancelled"
        return TraceSpanStatus(code="ERROR", message=str(reason))
    return TraceSpanStatus(code="UNSET")


def _extract_error_message(payload: Mapping[str, Any]) -> str | None:
    error_value = payload.get("error")
    if isinstance(error_value, Mapping):
        message = error_value.get("message")
        if message is not None:
            return str(message)
    if error_value is not None:
        return str(error_value)
    return None


def _preview_text(value: Any) -> str:
    return tracing_workflow._preview_text(value)  # type: ignore[attr-defined]  # noqa: SLF001


def _coalesce_status(payload: Mapping[str, Any]) -> str | None:
    return tracing_workflow._coalesce_status(payload)  # type: ignore[attr-defined]  # noqa: SLF001


def _extract_token_usage(payload: Mapping[str, Any]) -> tuple[int | None, int | None]:
    return tracing_workflow._extract_token_usage(payload)  # type: ignore[attr-defined]  # noqa: SLF001


def _extract_latency(payload: Mapping[str, Any]) -> int | None:
    return tracing_workflow._extract_latency(payload)  # type: ignore[attr-defined]  # noqa: SLF001


__all__ = [
    "build_trace_response",
    "build_trace_update",
]
