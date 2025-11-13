"""Workflow execution tracing helpers."""

from __future__ import annotations
from collections.abc import Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from opentelemetry import trace
from opentelemetry.trace import Span, SpanKind, Status, StatusCode
from orcheo.config.telemetry_settings import TelemetrySettings
from orcheo.tracing import configure_global_tracing
from orcheo_backend.app.history import RunHistoryStore


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class WorkflowTraceManager:
    """Manage OpenTelemetry spans for workflow executions."""

    def __init__(
        self,
        history_store: RunHistoryStore,
        *,
        workflow_id: str,
        execution_id: str,
        settings: TelemetrySettings,
    ) -> None:
        """Initialise the manager for a workflow execution."""
        self._history_store = history_store
        self._workflow_id = workflow_id
        self._execution_id = execution_id
        self._settings = settings
        self._enabled = settings.enabled
        self._tracer = trace.get_tracer("orcheo.backend.workflow")
        self._root_span: Span | None = None
        self._active_spans: dict[str, Span] = {}

    @asynccontextmanager
    async def workflow_span(self) -> Any:
        """Create the root workflow span if tracing is enabled."""
        if not self._enabled:
            yield None
            return

        provider = configure_global_tracing(self._settings, force=False)
        if provider is not None:
            self._tracer = trace.get_tracer("orcheo.backend.workflow")
        start_time = _utcnow()
        span_cm = self._tracer.start_as_current_span(
            "Workflow Execution",
            kind=SpanKind.SERVER,
            attributes={
                "orcheo.execution.id": self._execution_id,
                "orcheo.workflow.id": self._workflow_id,
            },
        )
        with span_cm as span:
            self._root_span = span
            span.set_attribute("orcheo.execution.status", "running")
            await self._history_store.update_trace_metadata(
                self._execution_id,
                trace_id=_format_trace_id(span),
                started_at=start_time,
                updated_at=start_time,
            )
            try:
                yield span
            finally:
                await self._history_store.update_trace_metadata(
                    self._execution_id, updated_at=_utcnow()
                )
                self._finalize_active_spans()
                self._root_span = None

    async def record_step(self, step: Mapping[str, Any]) -> None:
        """Record a node step as a child span when tracing is enabled."""
        if not self._enabled or self._root_span is None:
            return

        timestamp = _utcnow()
        await self._history_store.update_trace_metadata(
            self._execution_id, updated_at=timestamp
        )

        event = _as_str(step.get("event"))
        node_name = _as_str(step.get("node") or step.get("name"))
        payload = _ensure_mapping(step.get("payload") or step.get("data"))
        node_key = _resolve_node_key(step, payload)

        if event is None or node_name is None:
            return

        if event == "on_chain_start":
            self._handle_start_event(node_name, step, payload, node_key)
            return

        if event in {"on_chain_end", "on_chain_error"}:
            self._handle_completion_event(node_name, step, payload, node_key, event)
            return

        if event == "on_chain_stream":
            self._handle_stream_event(node_key, payload)

    async def mark_workflow_status(
        self,
        status: str,
        *,
        reason: str | None = None,
        finalize: bool = False,
    ) -> None:
        """Annotate the root span with workflow status information."""
        if not self._enabled or self._root_span is None:
            return

        self._root_span.set_attribute("orcheo.execution.status", status)
        if reason:
            self._root_span.add_event(
                "workflow.status",
                {"status": status, "reason": reason},
            )
        if finalize:
            if status == "error":
                self._finalize_active_spans(status="error")
            elif status == "cancelled":
                self._finalize_active_spans(status="cancelled")
            else:
                self._finalize_active_spans(status="success")
        await self._history_store.update_trace_metadata(
            self._execution_id, updated_at=_utcnow()
        )

    async def record_workflow_error(self, error: Exception) -> None:
        """Record an error on the root span."""
        if not self._enabled or self._root_span is None:
            return
        self._root_span.record_exception(error)
        self._root_span.set_status(Status(StatusCode.ERROR, str(error)))
        await self.mark_workflow_status("error", reason=str(error), finalize=True)

    def _finalize_active_spans(self, *, status: str | None = None) -> None:
        if not self._active_spans:
            return
        final_status = status or "cancelled"
        for span in self._active_spans.values():
            span.set_attribute("orcheo.node.status", final_status)
            span.end()
        self._active_spans.clear()

    def _handle_start_event(
        self,
        node_name: str,
        step: Mapping[str, Any],
        payload: Mapping[str, Any],
        node_key: str,
    ) -> None:
        span_name, attributes = _build_node_metadata(node_name, step, payload)
        root_span = self._root_span
        if root_span is None:
            return
        context = trace.set_span_in_context(root_span)
        span = self._tracer.start_span(
            span_name,
            context=context,
            kind=SpanKind.INTERNAL,
            attributes=attributes,
        )
        span.set_attribute("orcheo.node.status", "running")
        self._active_spans[node_key] = span

    def _handle_completion_event(
        self,
        node_name: str,
        step: Mapping[str, Any],
        payload: Mapping[str, Any],
        node_key: str,
        event: str,
    ) -> None:
        span = self._active_spans.pop(node_key, None)
        span_name, attributes = _build_node_metadata(node_name, step, payload)
        if span is None:
            root_span = self._root_span
            if root_span is None:
                return
            context = trace.set_span_in_context(root_span)
            span = self._tracer.start_span(
                span_name,
                context=context,
                kind=SpanKind.INTERNAL,
                attributes=attributes,
            )
        else:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        tokens = _attach_token_metrics(span, payload)
        _attach_artifacts(span, payload)
        _attach_messages(span, payload)

        if event == "on_chain_error":
            error_message = _as_str(payload.get("error"))
            if error_message:
                span.record_exception(RuntimeError(error_message))
            error_code = _as_str(payload.get("error_code"))
            if error_code:
                span.set_attribute("orcheo.error.code", error_code)
            span.set_status(Status(StatusCode.ERROR, error_message))
            span.set_attribute("orcheo.node.status", "error")
        else:
            span.set_status(Status(StatusCode.OK))
            span.set_attribute("orcheo.node.status", "success")

        if tokens and any(value is not None and value > 1000 for value in tokens):
            span.add_event(
                "token.chunk",
                {
                    "input": tokens[0] or 0,
                    "output": tokens[1] or 0,
                    "reason": "high_usage",
                },
            )

        span.end()

    def _handle_stream_event(self, node_key: str, payload: Mapping[str, Any]) -> None:
        span = self._active_spans.get(node_key)
        if span is None:
            return
        stream_payload = payload.get("data") or payload
        if stream_payload:
            span.add_event(
                "stream", {"payload": _truncate(str(stream_payload), limit=256)}
            )


def _resolve_node_key(step: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    candidate = payload.get("node_id") or step.get("node_id") or step.get("node")
    return _as_str(candidate) or "unknown"


def _build_node_metadata(
    node_name: str,
    step: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    node_id = _as_str(payload.get("node_id") or step.get("node_id") or node_name)
    display_name = _as_str(payload.get("display_name") or step.get("display_name"))
    node_kind = _as_str(
        payload.get("type") or payload.get("kind") or step.get("node_type")
    )
    span_name = display_name or node_name
    attributes: dict[str, Any] = {
        "orcheo.node.id": node_id,
        "orcheo.node.display_name": span_name,
    }
    if node_kind:
        attributes["orcheo.node.kind"] = node_kind
    return span_name, attributes


def _attach_token_metrics(
    span: Span,
    payload: Mapping[str, Any],
) -> tuple[int | None, int | None]:
    tokens = payload.get("token_usage") or payload.get("tokens")
    if not isinstance(tokens, Mapping):
        return (None, None)
    input_tokens = _to_int(tokens.get("input"))
    output_tokens = _to_int(tokens.get("output"))
    if input_tokens is not None:
        span.set_attribute("orcheo.token.input", input_tokens)
    if output_tokens is not None:
        span.set_attribute("orcheo.token.output", output_tokens)
    return (input_tokens, output_tokens)


def _attach_artifacts(span: Span, payload: Mapping[str, Any]) -> None:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        return
    artifact_ids: list[str] = []
    for artifact in artifacts:
        if isinstance(artifact, Mapping):
            if "id" in artifact:
                artifact_ids.append(str(artifact["id"]))
        else:
            artifact_ids.append(str(artifact))
    if artifact_ids:
        span.set_attribute("orcheo.artifact.ids", artifact_ids)


def _attach_messages(span: Span, payload: Mapping[str, Any]) -> None:
    prompt = _as_str(payload.get("prompt"))
    response = _as_str(payload.get("response"))
    if prompt:
        span.add_event("message", {"role": "user", "content": _truncate(prompt)})
    if response:
        span.add_event(
            "message",
            {"role": "assistant", "content": _truncate(response)},
        )


def _format_trace_id(span: Span) -> str:
    context = span.get_span_context()
    return f"{context.trace_id:032x}"


def _ensure_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _truncate(value: str, *, limit: int = 512) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}…"


__all__ = ["WorkflowTraceManager"]
