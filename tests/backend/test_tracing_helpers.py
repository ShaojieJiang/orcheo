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


def _install_in_memory_exporter() -> tuple[
    InMemorySpanExporter, TracerProvider, SimpleSpanProcessor
]:
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
    provider.add_span_processor(processor)
    exporter.clear()
    return exporter, provider, processor


def test_build_step_span_attributes_truncates_large_collections() -> None:
    prompts = [f"prompt-{index}" for index in range(30)]
    payload: dict[str, Any] = {
        "node-1": {
            "prompts": prompts,
            "responses": ["response" * 1000],
        }
    }

    attributes = build_step_span_attributes(payload)

    prompt_attributes = attributes["orcheo.step.prompts"]
    assert len(prompt_attributes) == 26
    assert prompt_attributes[-1] == "...(+5 more)"
    assert prompt_attributes[0] == "prompt-0"
    assert prompt_attributes[24] == "prompt-24"

    response_attributes = attributes["orcheo.step.responses"]
    assert response_attributes[0].endswith("…")
    assert len(response_attributes[0]) == 2048


def test_derive_step_span_name_prefers_node_identifier() -> None:
    payload = {"node-a": {"status": "running"}}
    assert derive_step_span_name(3, payload) == "workflow.step.node-a"
    assert derive_step_span_name(4, {}) == "workflow.step.4"


def test_workflow_execution_span_provides_trace_ids() -> None:
    exporter, provider, processor = _install_in_memory_exporter()

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
        provider.force_flush()
        finished = exporter.get_finished_spans()
        assert any(span.name == "workflow.execution" for span in finished)
    finally:
        processor.shutdown()


def test_workflow_execution_span_truncates_large_attributes() -> None:
    exporter, provider, processor = _install_in_memory_exporter()
    large_payload = {"data": "x" * 3000}

    try:
        with workflow_execution_span(
            "wf-id",
            "exec-id",
            inputs=large_payload,
        ) as trace_ctx:
            trace_ctx.set_final_state(large_payload)

        provider.force_flush()
        finished = exporter.get_finished_spans()
        root_span = next(span for span in finished if span.name == "workflow.execution")
        inputs_attr = root_span.attributes["orcheo.workflow.inputs"]
        final_state_attr = root_span.attributes["orcheo.workflow.final_state"]

        assert len(inputs_attr) == 2048
        assert inputs_attr.endswith("…")
        assert len(final_state_attr) == 2048
        assert final_state_attr.endswith("…")
    finally:
        processor.shutdown()
