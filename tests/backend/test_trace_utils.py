"""Unit tests for trace utilities."""

from __future__ import annotations
from datetime import UTC, datetime
from hashlib import blake2b
from typing import Any
import pytest
from orcheo_backend.app import trace_utils
from orcheo_backend.app.history.models import RunHistoryRecord
from orcheo_backend.app.schemas.traces import TraceSpanResponse
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


def test_trace_update_short_trace_id_still_generates_digest_span() -> None:
    """Trace updates should fall back to digest spans when trace_id is too short."""

    record = RunHistoryRecord(
        workflow_id="wf-short",
        execution_id="exec-short",
        status="running",
        trace_id="abcd-1234",
    )
    record.trace_started_at = _timestamp()

    update = build_trace_update(record, include_root=True)

    assert update is not None
    assert len(update.spans) == 1
    expected_root_id = blake2b(
        f"{record.execution_id}:root".encode(), digest_size=8
    ).hexdigest()
    assert update.spans[0].span_id == expected_root_id
    assert update.trace_id == record.trace_id


def test_node_attributes_include_status_and_latency() -> None:
    """_node_attributes should surface normalized status and latency metadata."""

    payload = {"id": "node", "status": "SUCCESS", "latency_ms": 37}

    attributes = trace_utils._node_attributes("node", payload)

    assert attributes["orcheo.node.status"] == "success"
    assert attributes["orcheo.node.latency_ms"] == 37


def test_extract_artifact_ids_handles_non_mapping_entries() -> None:
    """_extract_artifact_ids should coerce non-mapping artifacts to strings."""

    payload = {"artifacts": ["artifact-a", {"id": "artifact-b"}]}

    artifact_ids = trace_utils._extract_artifact_ids(payload)

    assert artifact_ids == ["artifact-a", "artifact-b"]


def test_build_text_events_for_sequence_values() -> None:
    """_build_text_events should emit an event per list entry."""

    default_time = _timestamp()

    events = trace_utils._build_text_events(
        "response",
        ["first", "second"],
        default_time,
    )

    assert [event.attributes["preview"] for event in events] == ["first", "second"]


def test_status_from_payload_handles_missing_status() -> None:
    """_status_from_payload should return UNSET when no status metadata is present."""

    status = trace_utils._status_from_payload({})

    assert status.code == "UNSET"
    assert status.message is None


def test_status_from_payload_handles_cancellation_reason() -> None:
    """_status_from_payload should surface cancellation reasons in status message."""

    status = trace_utils._status_from_payload(
        {"status": "cancelled", "reason": "user request"}
    )

    assert status.code == "ERROR"
    assert status.message == "user request"


def test_extract_error_message_handles_primitives_and_missing() -> None:
    """Should stringify primitives and return None when absent."""

    assert trace_utils._extract_error_message({"error": 404}) == "404"
    assert trace_utils._extract_error_message({}) is None


def test_build_spans_for_step_skips_none_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_build_spans_for_step should ignore nodes that returned no span."""

    record = RunHistoryRecord(workflow_id="wf", execution_id="exec", status="running")
    step = record.append_step({"node-a": {}, "node-b": {}}, at=_timestamp())

    def fake_build_node_span(
        record_arg: RunHistoryRecord,
        step_arg: Any,
        node_key: str,
        payload: dict[str, Any],
        parent_id: str,
    ) -> TraceSpanResponse | None:
        if node_key == "node-a":
            return None
        return TraceSpanResponse(
            span_id="child",
            parent_span_id=parent_id,
            name=node_key,
        )

    monkeypatch.setattr(trace_utils, "_build_node_span", fake_build_node_span)

    spans = trace_utils._build_spans_for_step(record, step, "root")

    assert [span.name for span in spans] == ["node-b"]


def test_node_attributes_omits_optional_metadata() -> None:
    """_node_attributes should skip status/latency keys when unavailable."""

    attributes = trace_utils._node_attributes("node", {})

    assert "orcheo.node.status" not in attributes
    assert "orcheo.node.latency_ms" not in attributes


def test_build_text_events_handles_scalars() -> None:
    """_build_text_events should cover scalar fallbacks for preview strings."""

    default_time = _timestamp()

    events = trace_utils._build_text_events("prompt", "answer", default_time)

    assert len(events) == 1
    assert events[0].attributes["preview"] == "answer"


def test_status_from_payload_returns_unset_for_unknown_states() -> None:
    """_status_from_payload should default to UNSET for non terminal states."""

    status = trace_utils._status_from_payload({"status": "pending"})

    assert status.code == "UNSET"


def test_extract_error_message_prefers_mapping_message() -> None:
    """_extract_error_message should prefer nested mapping messages."""

    message = trace_utils._extract_error_message(
        {"error": {"message": "detailed boom", "code": 500}}
    )

    assert message == "detailed boom"


def test_extract_error_message_falls_back_to_mapping_repr() -> None:
    """_extract_error_message should stringify mapping payloads without message."""

    message = trace_utils._extract_error_message({"error": {"code": "MISSING"}})

    assert message == "{'code': 'MISSING'}"
