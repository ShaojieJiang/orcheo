"""Tests for workflow tracing helpers."""

from __future__ import annotations
from typing import Any
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode, Tracer
from orcheo import config
from orcheo.tracing import workflow as workflow_module
from orcheo.tracing.workflow import record_workflow_step, workflow_span


def _build_tracer() -> tuple[Tracer, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(__name__)
    return tracer, exporter


class _RecordingSpan:
    """Lightweight span stub that records events and attributes for assertions."""

    def __init__(self) -> None:
        self.status: Any = None
        self.attributes: dict[str, Any] = {}
        self.events: list[tuple[str, dict[str, Any] | None]] = []

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.events.append((name, attributes))

    def set_status(self, status: Any) -> None:
        self.status = status


def test_record_workflow_step_creates_child_span() -> None:
    tracer, exporter = _build_tracer()
    step_payload = {
        "node-1": {
            "display_name": "AI Model Node",
            "status": "success",
            "token_usage": {"input": 42, "output": 10},
            "prompts": ["hello"],
            "responses": ["world"],
            "artifacts": ["artifact-1"],
        }
    }

    with tracer.start_as_current_span("workflow.execution"):
        record_workflow_step(tracer, step_payload)

    spans = exporter.get_finished_spans()
    assert len(spans) == 2
    child = next(span for span in spans if span.name != "workflow.execution")
    assert child.attributes["orcheo.node.display_name"] == "AI Model Node"
    assert child.attributes["orcheo.token.input"] == 42
    assert child.attributes["orcheo.token.output"] == 10
    assert child.attributes["orcheo.artifact.ids"] == ("artifact-1",)
    event_names = {event.name for event in child.events}
    assert "prompt" in event_names
    assert "response" in event_names


def test_workflow_span_captures_execution_metadata() -> None:
    tracer, exporter = _build_tracer()

    with workflow_span(
        tracer,
        workflow_id="wf",
        execution_id="exec",
        inputs={"foo": "bar"},
    ) as span_context:
        span_context.span.add_event("test")
        trace_id = span_context.trace_id

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    root = spans[0]
    assert root.attributes["orcheo.execution.id"] == "exec"
    assert root.attributes["orcheo.workflow.id"] == "wf"
    assert root.attributes["orcheo.execution.input_keys"] == ("foo",)
    assert trace_id


def test_high_token_threshold_uses_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORCHEO_TRACING_HIGH_TOKEN_THRESHOLD", "10")
    config.get_settings(refresh=True)

    tracer, exporter = _build_tracer()
    step_payload = {
        "node-1": {
            "display_name": "AI Model Node",
            "status": "success",
            "token_usage": {"input": 11, "output": 3},
        }
    }

    with tracer.start_as_current_span("workflow.execution"):
        record_workflow_step(tracer, step_payload)

    spans = exporter.get_finished_spans()
    child = next(span for span in spans if span.name != "workflow.execution")
    token_events = [event for event in child.events if event.name == "token.chunk"]
    assert token_events and token_events[0].attributes["input"] == 11

    monkeypatch.delenv("ORCHEO_TRACING_HIGH_TOKEN_THRESHOLD", raising=False)
    config.get_settings(refresh=True)


def test_preview_text_redacts_sensitive_information(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORCHEO_TRACING_PREVIEW_MAX_LENGTH", "128")
    config.get_settings(refresh=True)

    tracer, exporter = _build_tracer()
    step_payload = {
        "node-1": {
            "display_name": "AI Model Node",
            "status": "success",
            "responses": ["Contact us at user@example.com"],
            "messages": [
                {"role": "system", "content": "api_token = super-secret-value"}
            ],
        }
    }

    with tracer.start_as_current_span("workflow.execution"):
        record_workflow_step(tracer, step_payload)

    spans = exporter.get_finished_spans()
    child = next(span for span in spans if span.name != "workflow.execution")
    for event in child.events:
        for value in event.attributes.values():
            assert "user@example.com" not in str(value)
            assert "super-secret-value" not in str(value)
    redactions = [
        attr
        for event in child.events
        for attr in event.attributes.values()
        if "[REDACTED]" in str(attr)
    ]
    assert redactions

    monkeypatch.delenv("ORCHEO_TRACING_PREVIEW_MAX_LENGTH", raising=False)
    config.get_settings(refresh=True)


def test_record_workflow_step_records_error_metadata_and_messages() -> None:
    tracer, exporter = _build_tracer()
    config.get_settings(refresh=True)
    long_error = "x" * 600
    step_payload = {
        "node-1": {
            "display_name": "AI Model Node",
            "kind": "tool",
            "state": "ERROR",
            "duration_ms": "42",
            "error": {"code": "E123", "message": long_error},
            "messages": [
                {"role": "user", "content": "hello world"},
                "fallback message",
            ],
            "prompt": {"text": "secret=should-redact"},
            "prompts": ["extra prompt"],
            "responses": ["response-one"],
            "response": "single response",
            "artifacts": [
                {"id": "artifact-2"},
                {"name": "no-id"},
                "artifact-3",
            ],
            "usage": {"completion": "7"},
            "usage_metadata": {"prompt_tokens": "5"},
            "input_tokens": "3",
        }
    }

    with tracer.start_as_current_span("workflow.execution"):
        record_workflow_step(tracer, step_payload)

    spans = exporter.get_finished_spans()
    child = next(span for span in spans if span.name != "workflow.execution")
    assert child.attributes["orcheo.node.kind"] == "tool"
    assert child.attributes["orcheo.node.status"] == "error"
    assert child.attributes["orcheo.node.latency_ms"] == 42
    assert child.attributes["orcheo.error.code"] == "E123"
    assert child.attributes["orcheo.token.input"] == 5
    assert child.attributes["orcheo.token.output"] == 7
    assert child.attributes["orcheo.artifact.ids"] == (
        "artifact-2",
        "{'name': 'no-id'}",
        "artifact-3",
    )
    error_details = [event for event in child.events if event.name == "error.detail"]
    assert error_details
    preview_length = config.get_settings().tracing_preview_max_length
    assert error_details[0].attributes["message"].endswith("…")
    assert len(error_details[0].attributes["message"]) == preview_length
    message_events = [event for event in child.events if event.name == "message"]
    assert len(message_events) == 2
    prompt_events = [event for event in child.events if event.name == "prompt"]
    assert prompt_events
    response_events = [event for event in child.events if event.name == "response"]
    assert response_events
    assert child.status.status_code is StatusCode.ERROR


def test_node_attributes_omits_status_when_missing() -> None:
    attributes = workflow_module._node_attributes(
        "node-1",
        {"display_name": "AI Model Node", "kind": "ai_model"},
    )

    assert "orcheo.node.status" not in attributes


def test_apply_message_events_ignores_non_sequence_messages() -> None:
    span = _RecordingSpan()

    workflow_module._apply_message_events(span, {"messages": 123})

    assert not span.events


def test_apply_status_returns_when_status_missing() -> None:
    span = _RecordingSpan()
    workflow_module._apply_status(span, {})

    assert span.status is None
    assert not span.events


def test_apply_status_handles_string_error_message() -> None:
    span = _RecordingSpan()

    workflow_module._apply_status(span, {"status": "error", "error": "string failure"})

    assert span.status.status_code is StatusCode.ERROR
    assert span.status.description == "string failure"
    error_events = [event for event in span.events if event[0] == "error.detail"]
    assert error_events
    assert error_events[0][1]["message"].startswith("string failure")


def test_apply_status_handles_error_code_without_message() -> None:
    span = _RecordingSpan()

    workflow_module._apply_status(
        span,
        {
            "status": "error",
            "error": {"code": "E321"},
        },
    )

    assert span.attributes["orcheo.error.code"] == "E321"
    assert not [event for event in span.events if event[0] == "error.detail"]
    assert span.status.status_code is StatusCode.ERROR
    assert span.status.description == "error"


def test_apply_status_handles_missing_error_object() -> None:
    span = _RecordingSpan()

    workflow_module._apply_status(span, {"status": "error"})

    assert span.status.status_code is StatusCode.ERROR
    assert span.status.description == "error"
    assert not span.events


def test_extract_token_usage_prefers_nested_sources() -> None:
    payload = {
        "token_usage": {"input_tokens": "9", "output_tokens": 2},
        "usage": {"completion": "7"},
        "usage_metadata": {"prompt_tokens": "5"},
    }

    input_tokens, output_tokens = workflow_module._extract_token_usage(payload)

    assert input_tokens == 9
    assert output_tokens == 2


def test_extract_token_usage_falls_back_to_top_level_fields() -> None:
    payload = {
        "token_usage": None,
        "usage": None,
        "usage_metadata": "not-a-mapping",
        "input_tokens": "4",
        "completion_tokens": 3,
    }

    input_tokens, output_tokens = workflow_module._extract_token_usage(payload)

    assert input_tokens == 4
    assert output_tokens == 3


def test_preview_text_truncates_long_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ORCHEO_TRACING_PREVIEW_MAX_LENGTH", raising=False)
    settings = config.get_settings(refresh=True)
    value = "a" * (settings.tracing_preview_max_length + 25)

    preview = workflow_module._preview_text(value)

    assert preview.endswith("…")
    assert len(preview) == settings.tracing_preview_max_length
