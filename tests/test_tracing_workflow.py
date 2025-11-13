"""Tests for workflow tracing helpers."""

from __future__ import annotations

from typing import Tuple

import pytest

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import Tracer

from orcheo import config
from orcheo.tracing.workflow import record_workflow_step, workflow_span


def _build_tracer() -> Tuple[Tracer, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(__name__)
    return tracer, exporter


def test_record_workflow_step_creates_child_span() -> None:
    tracer, exporter = _build_tracer()
    step_payload = {
        "node-1": {
            "display_name": "LLM Node",
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
    assert child.attributes["orcheo.node.display_name"] == "LLM Node"
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
            "display_name": "LLM Node",
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
            "display_name": "LLM Node",
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
