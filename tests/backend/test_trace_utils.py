"""Unit tests for trace utilities."""

from __future__ import annotations
from datetime import UTC, datetime
from hashlib import blake2b
from orcheo_backend.app.history.models import RunHistoryRecord
from orcheo_backend.app.trace_utils import build_trace_response, build_trace_update


def _timestamp(offset_seconds: int = 0) -> datetime:
    return datetime(2024, 1, 1, 12, 0, offset_seconds, tzinfo=UTC)


def test_build_trace_response_emits_span_metadata() -> None:
    """build_trace_response should return root and child span details."""

    record = RunHistoryRecord(
        workflow_id="wf-1",
        execution_id="exec-1",
        status="completed",
    )
    record.trace_started_at = _timestamp()
    record.trace_completed_at = _timestamp(5)
    record.append_step(
        {
            "llm": {
                "id": "node-1",
                "display_name": "Draft",
                "kind": "llm",
                "status": "completed",
                "latency_ms": 42,
                "token_usage": {"input": 5, "output": 7},
                "artifacts": [{"id": "artifact-1"}],
                "prompts": {"text": "Hello"},
                "responses": ["World"],
                "messages": [
                    {"role": "assistant", "content": "Hi there"},
                    "plain message",
                ],
            },
            "status": "ignored",
        },
        at=_timestamp(1),
    )

    response = build_trace_response(record)
    assert response.execution.id == "exec-1"
    assert response.execution.token_usage.input == 5
    assert response.execution.token_usage.output == 7

    assert len(response.spans) == 2
    root_span, node_span = response.spans
    assert root_span.parent_span_id is None
    assert root_span.attributes["orcheo.execution.id"] == "exec-1"
    assert len(node_span.events) == 4  # prompt, response, two message events
    assert node_span.attributes["orcheo.node.kind"] == "llm"
    assert node_span.attributes["orcheo.token.output"] == 7
    assert node_span.attributes["orcheo.artifact.ids"] == ["artifact-1"]
    assert node_span.status.code == "OK"


def test_build_trace_update_returns_none_for_non_node_payload() -> None:
    """build_trace_update should return None when no spans are generated."""

    record = RunHistoryRecord(workflow_id="wf", execution_id="exec", status="running")
    step = record.append_step({"status": "running"}, at=_timestamp())

    update = build_trace_update(record, step=step)
    assert update is None


def test_build_trace_update_includes_root_and_error_status() -> None:
    """build_trace_update should include root span and child error metadata."""

    record = RunHistoryRecord(
        workflow_id="wf-err",
        execution_id="exec-err",
        status="error",
        trace_id="12345678-90ab-cdef-1234-567890abcdef",
    )
    record.trace_started_at = _timestamp()
    step = record.append_step(
        {
            "node": {
                "status": "error",
                "error": {"message": "boom"},
            }
        },
        at=_timestamp(2),
    )
    record.error = "boom"

    update = build_trace_update(record, step=step, include_root=True, complete=True)
    assert update is not None
    assert update.complete is True
    assert update.trace_id == record.trace_id
    assert len(update.spans) == 2
    root_span, child_span = update.spans
    assert root_span.span_id == record.trace_id.replace("-", "")[:16]
    assert child_span.status.code == "ERROR"
    assert child_span.status.message == "boom"


def test_build_trace_update_complete_without_spans_emits_message() -> None:
    """Completion updates should emit even when no span changes occurred."""

    record = RunHistoryRecord(
        workflow_id="wf-complete",
        execution_id="exec-complete",
        status="completed",
    )
    record.trace_started_at = _timestamp()
    record.trace_completed_at = _timestamp(10)

    update = build_trace_update(record, include_root=False, complete=True)

    assert update is not None
    assert update.complete is True
    assert update.spans == []

    expected_trace_id = blake2b(
        f"{record.execution_id}:root".encode(), digest_size=8
    ).hexdigest()
    assert update.trace_id == expected_trace_id


def test_trace_update_root_span_uses_digest_when_missing_trace_id() -> None:
    """Trace updates should derive a deterministic root ID when trace_id is absent."""

    record = RunHistoryRecord(
        workflow_id="wf-fallback",
        execution_id="exec-fallback",
        status="running",
    )
    record.trace_started_at = _timestamp()

    update = build_trace_update(record, include_root=True)

    assert update is not None
    assert len(update.spans) == 1

    root_span = update.spans[0]
    expected_root_id = blake2b(
        f"{record.execution_id}:root".encode(), digest_size=8
    ).hexdigest()
    assert root_span.span_id == expected_root_id
    assert update.trace_id == expected_root_id
