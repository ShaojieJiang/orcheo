"""Helpers for converting run history data into API responses."""

from __future__ import annotations
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from orcheo.models import CredentialHealthStatus
from orcheo.vault.oauth import CredentialHealthReport
from orcheo_backend.app.history import RunHistoryRecord, RunHistoryStep
from orcheo_backend.app.schemas.credentials import (
    CredentialHealthItem,
    CredentialHealthResponse,
)
from orcheo_backend.app.schemas.runs import (
    RunHistoryResponse,
    RunHistoryStepResponse,
    RunTraceExecutionSummary,
    RunTracePageInfo,
    RunTraceResponse,
    RunTraceSpan,
    RunTraceSpanEvent,
    RunTraceSpanStatus,
    RunTraceUpdateMessage,
)


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


def trace_to_response(record: RunHistoryRecord) -> RunTraceResponse:
    """Convert a history record into a trace response payload."""
    builder = _TraceBuilder(record)
    spans = builder.build_spans()
    execution_summary = RunTraceExecutionSummary(
        execution_id=record.execution_id,
        workflow_id=record.workflow_id,
        status=record.status,
        started_at=record.trace_started_at or record.started_at,
        completed_at=record.trace_completed_at or record.completed_at,
        error=record.error,
        trace_id=record.trace_id,
        token_usage=builder.token_usage_summary,
    )
    return RunTraceResponse(
        execution=execution_summary,
        spans=spans,
        page_info=RunTracePageInfo(has_next_page=False, cursor=None),
    )


def trace_update_from_step(
    *,
    record: RunHistoryRecord,
    step: RunHistoryStep | None,
    complete: bool = False,
) -> RunTraceUpdateMessage | None:
    """Return a websocket update payload for the provided history step."""
    builder = _TraceBuilder(record)
    spans = builder.build_spans_from_step(step) if step is not None else []
    if complete:
        spans.insert(0, builder.build_root_span())
    if not spans and not complete:
        return None
    return RunTraceUpdateMessage(
        execution_id=record.execution_id,
        trace_id=record.trace_id,
        spans=spans,
        complete=complete,
    )


class _TraceBuilder:
    """Helper responsible for converting history records to span payloads."""

    _DEFAULT_MAX_PREVIEW_LENGTH = 512
    _SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(r"(?i)\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b"),
        re.compile(r"\\b\\d{3}[-.\\s]?\\d{2}[-.\\s]?\\d{4}\\b"),
        re.compile(r"\\b(?:\\d[ -.]){13,16}\\b"),
    )
    _SECRET_ASSIGNMENT_PATTERN = re.compile(
        r"(?i)\\b(?P<label>(?:api|secret|token|key)[\\w-]*)\\s*(?P<sep>[:=])\\s*(?P<value>[A-Z0-9\\-_=]{8,})"
    )

    def __init__(self, record: RunHistoryRecord) -> None:
        self._record = record
        self._trace_id = record.trace_id or record.execution_id
        self._root_span_id = f"{self._trace_id}:root"
        self._token_input = 0
        self._token_output = 0

    @property
    def token_usage_summary(self) -> dict[str, int] | None:
        summary: dict[str, int] = {}
        if self._token_input:
            summary["input"] = self._token_input
        if self._token_output:
            summary["output"] = self._token_output
        return summary or None

    def build_spans(self) -> list[RunTraceSpan]:
        spans = [self.build_root_span()]
        for step in self._record.steps:
            spans.extend(self.build_spans_from_step(step))
        return spans

    def build_spans_from_step(self, step: RunHistoryStep) -> list[RunTraceSpan]:
        spans: list[RunTraceSpan] = []
        for node_name, payload in step.payload.items():
            if not isinstance(payload, Mapping):
                continue
            span = self._build_child_span(node_name, payload, step)
            if span is not None:
                spans.append(span)
        return spans

    def build_root_span(self) -> RunTraceSpan:
        start_time = self._record.trace_started_at or self._record.started_at
        end_time = self._record.trace_completed_at or self._record.completed_at
        attributes = {
            "orcheo.execution.id": self._record.execution_id,
            "orcheo.workflow.id": self._record.workflow_id,
        }
        status = self._map_status(self._record.status, error=self._record.error)
        return RunTraceSpan(
            span_id=self._root_span_id,
            parent_span_id=None,
            name="workflow.execution",
            start_time=start_time,
            end_time=end_time,
            attributes=attributes,
            status=status,
        )

    def _build_child_span(
        self,
        node_name: str,
        payload: Mapping[str, Any],
        step: RunHistoryStep,
    ) -> RunTraceSpan | None:
        span_id = self._build_span_id(node_name, step.index)
        name = str(payload.get("display_name", node_name))
        attributes: dict[str, Any] = {
            "orcheo.node.id": str(payload.get("id", node_name)),
            "orcheo.node.display_name": name,
        }
        node_kind = payload.get("kind") or payload.get("type")
        if node_kind is not None:
            attributes["orcheo.node.kind"] = str(node_kind)
        latency = self._extract_latency(payload)
        if latency is not None:
            attributes["orcheo.node.latency_ms"] = latency
        input_tokens, output_tokens = self._extract_token_usage(payload)
        if input_tokens is not None:
            attributes["orcheo.token.input"] = input_tokens
            self._token_input += input_tokens
        if output_tokens is not None:
            attributes["orcheo.token.output"] = output_tokens
            self._token_output += output_tokens
        artifact_ids = self._extract_artifact_ids(payload)
        if artifact_ids:
            attributes["orcheo.artifact.ids"] = artifact_ids

        status = self._map_status(payload.get("status"), error=payload.get("error"))
        events = self._build_events(payload, step.at)
        end_time = self._coalesce_end_time(payload, step.at)
        return RunTraceSpan(
            span_id=span_id,
            parent_span_id=self._root_span_id,
            name=name,
            start_time=step.at,
            end_time=end_time,
            attributes=attributes,
            events=events,
            status=status,
        )

    def _build_span_id(self, node_name: str, index: int) -> str:
        sanitized = re.sub(r"[^a-zA-Z0-9_.-]+", "-", node_name)
        return f"{self._trace_id}:{index}:{sanitized}"

    def _build_events(
        self,
        payload: Mapping[str, Any],
        at: datetime,
    ) -> list[RunTraceSpanEvent]:
        events: list[RunTraceSpanEvent] = []
        for key in ("prompts", "prompt"):
            if key in payload:
                events.extend(self._text_events("prompt", payload[key], at))
        for key in ("responses", "response"):
            if key in payload:
                events.extend(self._text_events("response", payload[key], at))
        if "messages" in payload:
            events.extend(self._message_events(payload["messages"], at))
        return events

    def _text_events(
        self,
        event_name: str,
        value: Any,
        at: datetime,
    ) -> list[RunTraceSpanEvent]:
        previews = self._coerce_sequence(value)
        if not previews:
            return []
        return [
            RunTraceSpanEvent(
                name=event_name,
                time=at,
                attributes={"preview": self._preview_text(item)},
            )
            for item in previews
        ]

    def _message_events(
        self,
        messages: Any,
        at: datetime,
    ) -> list[RunTraceSpanEvent]:
        if not isinstance(messages, Sequence) or isinstance(messages, (str, bytes)):
            return []
        events: list[RunTraceSpanEvent] = []
        for message in messages:
            if isinstance(message, Mapping):
                role = str(message.get("role", "message"))
                content = message.get("content")
            else:
                role = "message"
                content = message
            events.append(
                RunTraceSpanEvent(
                    name="message",
                    time=at,
                    attributes={
                        "role": role,
                        "preview": self._preview_text(content),
                    },
                )
            )
        return events

    def _coalesce_end_time(
        self,
        payload: Mapping[str, Any],
        default: datetime,
    ) -> datetime | None:
        end_time = payload.get("completed_at") or payload.get("end_time")
        if isinstance(end_time, datetime):
            return end_time
        if isinstance(end_time, str):
            try:
                return datetime.fromisoformat(end_time)
            except ValueError:  # pragma: no cover - defensive
                return None
        status = str(payload.get("status", "")).lower()
        if status in {"completed", "success", "ok", "error", "cancelled"}:
            return default
        return None

    def _map_status(
        self,
        status: Any,
        *,
        error: Any,
    ) -> RunTraceSpanStatus | None:
        if status is None:
            return None
        status_str = str(status)
        normalized = status_str.lower()
        if normalized in {"completed", "success", "ok"}:
            return RunTraceSpanStatus(code="OK")
        if normalized == "error":
            return RunTraceSpanStatus(code="ERROR", message=self._error_message(error))
        if normalized == "cancelled":
            message = self._error_message(error) or "cancelled"
            return RunTraceSpanStatus(code="ERROR", message=message)
        return RunTraceSpanStatus(code="UNSET")

    def _error_message(self, error: Any) -> str | None:
        if isinstance(error, Mapping):
            for key in ("message", "detail", "error"):
                value = error.get(key)
                if value:
                    return str(value)
        if isinstance(error, str):
            return error
        return None

    def _extract_latency(self, payload: Mapping[str, Any]) -> int | None:
        for key in ("latency_ms", "duration_ms", "elapsed_ms"):
            value = payload.get(key)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):  # pragma: no cover
                continue
        return None

    def _extract_token_usage(
        self, payload: Mapping[str, Any]
    ) -> tuple[int | None, int | None]:
        token_sources = (
            payload.get("token_usage"),
            payload.get("usage"),
            payload.get("usage_metadata"),
        )
        input_tokens = self._extract_token_count(token_sources, payload, True)
        output_tokens = self._extract_token_count(token_sources, payload, False)
        return input_tokens, output_tokens

    def _extract_token_count(
        self,
        sources: Sequence[Any],
        payload: Mapping[str, Any],
        is_input: bool,
    ) -> int | None:
        keys = (
            ("input", "input_tokens", "prompt", "prompt_tokens")
            if is_input
            else ("output", "output_tokens", "completion", "completion_tokens")
        )
        for source in sources:
            if not isinstance(source, Mapping):
                continue
            for key in keys:
                value = source.get(key)
                if value is None:
                    continue
                try:
                    return int(value)
                except (TypeError, ValueError):  # pragma: no cover
                    continue
        fallback_keys = keys[1:]  # skip the generic label to avoid duplicates
        for key in fallback_keys:
            candidate = payload.get(key)
            if candidate is None:
                continue
            try:
                return int(candidate)
            except (TypeError, ValueError):  # pragma: no cover
                continue
        return None

    def _extract_artifact_ids(self, payload: Mapping[str, Any]) -> list[str]:
        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, Sequence) or isinstance(artifacts, (str, bytes)):
            return []
        identifiers: list[str] = []
        for artifact in artifacts:
            if isinstance(artifact, Mapping):
                identifier = artifact.get("id")
                if identifier is not None:
                    identifiers.append(str(identifier))
            else:
                identifiers.append(str(artifact))
        return identifiers

    def _coerce_sequence(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, Mapping):
            return [v for v in value.values()]
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return list(value)
        return [value]

    def _preview_text(self, value: Any) -> str:
        text = "" if value is None else str(value)
        sanitized = self._sanitize_text(text)
        if len(sanitized) <= self._DEFAULT_MAX_PREVIEW_LENGTH:
            return sanitized
        return sanitized[: self._DEFAULT_MAX_PREVIEW_LENGTH - 1] + "…"

    def _sanitize_text(self, text: str) -> str:
        sanitized = text
        for pattern in self._SENSITIVE_PATTERNS:
            sanitized = pattern.sub("[REDACTED]", sanitized)

        def _replace_secret(match: re.Match[str]) -> str:
            label = match.group("label")
            separator = match.group("sep")
            return f"{label}{separator} [REDACTED]"

        return self._SECRET_ASSIGNMENT_PATTERN.sub(_replace_secret, sanitized)


__all__ = [
    "health_report_to_response",
    "history_to_response",
    "trace_to_response",
    "trace_update_from_step",
]
