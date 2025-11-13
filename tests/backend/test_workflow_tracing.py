"""Tests for workflow tracing helpers."""

from __future__ import annotations

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from orcheo.config.telemetry_settings import TelemetrySettings
from orcheo.tracing import get_configured_exporter, reset_tracing
from orcheo_backend.app.history import InMemoryRunHistoryStore
from orcheo_backend.app.tracing import WorkflowTraceManager


@pytest.mark.asyncio
async def test_workflow_trace_manager_records_spans() -> None:
    reset_tracing()
    store = InMemoryRunHistoryStore()
    await store.start_run(workflow_id="wf", execution_id="exec")

    settings = TelemetrySettings(
        enabled=True,
        exporter="inmemory",
        service_name="trace-test",
    )
    manager = WorkflowTraceManager(
        store,
        workflow_id="wf",
        execution_id="exec",
        settings=settings,
    )

    async with manager.workflow_span():
        await manager.record_step(
            {
                "event": "on_chain_start",
                "node": "Draft",
                "payload": {
                    "node_id": "node-1",
                    "display_name": "Draft Answer",
                    "type": "llm",
                },
            }
        )
        await manager.record_step(
            {
                "event": "on_chain_end",
                "node": "Draft",
                "payload": {
                    "node_id": "node-1",
                    "token_usage": {"input": 42, "output": 256},
                    "artifacts": ["artifact-1"],
                    "prompt": "Hello",
                    "response": "World",
                },
            }
        )
        await manager.mark_workflow_status("completed", finalize=True)

    exporter = get_configured_exporter()
    assert isinstance(exporter, InMemorySpanExporter)
    spans = exporter.get_finished_spans()
    assert len(spans) >= 2

    root_span = next(span for span in spans if span.name == "Workflow Execution")
    child_span = next(span for span in spans if span.name == "Draft Answer")

    assert root_span.attributes["orcheo.execution.id"] == "exec"
    assert root_span.attributes["orcheo.workflow.id"] == "wf"
    assert root_span.attributes["orcheo.execution.status"] == "completed"

    assert child_span.attributes["orcheo.node.id"] == "node-1"
    assert child_span.attributes["orcheo.token.input"] == 42
    assert child_span.attributes["orcheo.token.output"] == 256
    assert list(child_span.attributes["orcheo.artifact.ids"]) == ["artifact-1"]

    message_roles = {
        event.attributes.get("role")
        for event in child_span.events
        if event.name == "message"
    }
    assert {"user", "assistant"}.issubset(message_roles)

    history = await store.get_history("exec")
    assert history.trace_id is not None
    assert len(history.trace_id) == 32
    assert history.trace_started_at is not None
    assert history.trace_updated_at is not None
