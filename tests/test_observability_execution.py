"""Tests for execution viewer instrumentation."""

from __future__ import annotations

from datetime import timedelta

from orcheo.observability.execution import (
    ExecutionArtifact,
    ExecutionStep,
    ExecutionTrace,
)


def test_execution_trace_records_steps_and_totals() -> None:
    trace = ExecutionTrace(workflow_id="wf-1", run_id="run-1")
    step = trace.record_step(step_id="step-1", name="LLM", prompt="Hello")
    artifact = ExecutionArtifact(name="output.json", url="https://example.com/output.json")
    step.mark_completed(response="Hi", tokens=42, metrics={"latency_ms": 120.5}, artifacts=[artifact])

    assert trace.total_tokens() == 42
    assert trace.prompts() == ["Hello"]
    assert trace.responses() == ["Hi"]

    dashboard = trace.to_dashboard()
    assert dashboard["workflow_id"] == "wf-1"
    assert dashboard["total_tokens"] == 42
    assert dashboard["steps"][0]["artifacts"][0]["name"] == "output.json"
    assert dashboard["steps"][0]["duration_seconds"] is not None


def test_step_duration_is_none_until_completed() -> None:
    step = ExecutionStep(id="s-1", name="Task")
    assert step.duration_seconds is None
    step.completed_at = step.started_at + timedelta(seconds=2)
    assert step.duration_seconds == 2
