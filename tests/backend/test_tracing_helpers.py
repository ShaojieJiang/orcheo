from __future__ import annotations
import importlib
from typing import Any

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from orcheo_backend.app.tracing import (
    add_step_event,
    add_workflow_inputs_event,
    build_step_span_attributes,
    configure_tracing,
    format_trace_identifiers,
    get_workflow_tracer,
)


class DummySettings:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def get(self, key: str, default: Any | None = None) -> Any:
        return self._data.get(key, default)


class RecordingSpan:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any] | None]] = []

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.events.append((name, attributes))


def test_configure_tracing_uses_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_configure(**kwargs: Any) -> TracerProvider:
        captured.update(kwargs)
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        return provider

    tracing_module = importlib.import_module("orcheo_backend.app.tracing")
    monkeypatch.setattr(tracing_module, "configure_tracer_provider", fake_configure)

    settings = DummySettings(
        {
            "TRACING_EXPORTER": "console",
            "TRACING_SERVICE_NAME": "test-service",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "https://otel.local",
            "OTEL_EXPORTER_OTLP_HEADERS": {"authorization": "token"},
            "OTEL_EXPORTER_OTLP_INSECURE": False,
        }
    )

    configure_tracing(settings=settings)  # type: ignore[arg-type]

    assert captured["exporter"] == "console"
    assert captured["service_name"] == "test-service"
    assert captured["endpoint"] == "https://otel.local"
    assert captured["headers"] == {"authorization": "token"}
    assert captured["insecure"] is False


def test_build_step_span_attributes_extracts_metadata() -> None:
    payload = {
        "prompt": "Write a haiku",
        "response": {"content": "Code flows like water."},
        "usage": {"prompt_tokens": 12, "completion_tokens": "8", "total_tokens": 20},
        "artifacts": [
            {"id": "file-1"},
            {"id": "file-2"},
        ],
    }

    attributes = build_step_span_attributes(
        step_index=3,
        node_name="llm",
        payload=payload,
    )

    assert attributes["workflow.step.index"] == 3
    assert attributes["workflow.step.node"] == "llm"
    assert attributes["workflow.step.prompt"].startswith("Write a haiku")
    assert attributes["workflow.step.response"].startswith("Code flows")
    assert attributes["workflow.step.prompt_tokens"] == 12
    assert attributes["workflow.step.completion_tokens"] == 8
    assert attributes["workflow.step.total_tokens"] == 20
    assert attributes["workflow.step.artifact_count"] == 2
    assert attributes["workflow.step.artifact_ids"] == "file-1,file-2"


def test_step_and_input_events_are_recorded() -> None:
    span = RecordingSpan()
    add_workflow_inputs_event(span, {"input": "value"})
    add_step_event(
        span,
        step_index=1,
        node_name="tool",
        payload={"output": "result"},
    )

    assert span.events[0][0] == "workflow.inputs"
    assert "inputs" in span.events[0][1]
    assert span.events[1][0] == "workflow.step"
    assert span.events[1][1]["index"] == 1
    assert span.events[1][1]["node"] == "tool"


def test_format_trace_identifiers_returns_hex_strings() -> None:
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    tracer = get_workflow_tracer()

    with tracer.start_as_current_span("format-test") as span:
        trace_id, span_id = format_trace_identifiers(span)

    assert len(trace_id) == 32
    assert len(span_id) == 16
    int(trace_id, 16)
    int(span_id, 16)
