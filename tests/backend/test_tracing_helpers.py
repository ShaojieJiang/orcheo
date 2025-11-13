"""Tests for workflow tracing helpers."""

from __future__ import annotations

from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from orcheo.tracing import (
    build_step_span_attributes,
    derive_step_span_name,
    workflow_execution_span,
)


def test_build_step_span_attributes_extracts_metadata() -> None:
    payload: dict[str, Any] = {
        "node-1": {
            "prompt": "What is the weather?",
            "response": "It is sunny",
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "artifacts": ["artifact-1"],
        }
    }

    attributes = build_step_span_attributes(payload)
    assert attributes["orcheo.step.nodes"] == ["node-1"]
    assert attributes["orcheo.step.prompts"] == ["What is the weather?"]
    assert attributes["orcheo.step.responses"] == ["It is sunny"]
    assert attributes["orcheo.step.artifacts"] == ["artifact-1"]
    assert attributes["orcheo.step.token_usage.prompt_tokens"] == 10.0
    assert attributes["orcheo.step.token_usage.completion_tokens"] == 5.0


def test_derive_step_span_name_prefers_node_identifier() -> None:
    payload = {"node-a": {"status": "running"}}
    assert derive_step_span_name(3, payload) == "workflow.step.node-a"
    assert derive_step_span_name(4, {}) == "workflow.step.4"


def test_workflow_execution_span_provides_trace_ids() -> None:
    original_provider = trace.get_tracer_provider()
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    try:
        with workflow_execution_span(
            "wf-id",
            "exec-id",
            inputs={"foo": "bar"},
        ) as trace_ctx:
            assert trace_ctx.trace_id is not None
            assert trace_ctx.root_span_id is not None
            trace_ctx.set_execution_status("running")

            with trace_ctx.start_step_span(
                "workflow.step.node",
                attributes={"orcheo.step.status": "running"},
            ) as span:
                assert span is not None
                assert trace_ctx.span_id(span) is not None
        finished = exporter.get_finished_spans()
        assert any(span.name == "workflow.execution" for span in finished)
    finally:
        trace.set_tracer_provider(original_provider)
