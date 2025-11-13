"""Tests covering trace serialization helpers."""

from datetime import UTC, datetime, timedelta

from orcheo_backend.app.history.models import RunHistoryRecord, RunHistoryStep
from orcheo_backend.app.history_utils import trace_to_response, trace_update_from_step


def _base_record(status: str = "completed") -> RunHistoryRecord:
    started_at = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    record = RunHistoryRecord(
        workflow_id="wf-test",
        execution_id="exec-test",
        inputs={"foo": "bar"},
        status=status,
        trace_id="trace-abc",
        trace_started_at=started_at,
        trace_completed_at=started_at + timedelta(seconds=5),
        trace_last_span_at=started_at + timedelta(seconds=5),
    )
    return record


def test_trace_to_response_populates_span_metadata() -> None:
    """trace_to_response should derive span attributes and events from history."""

    record = _base_record()
    first_step_at = record.trace_started_at + timedelta(seconds=1)  # type: ignore[operator]
    record.append_step(
        {
            "llm": {
                "id": "node-1",
                "display_name": "LLM Node",
                "kind": "tool",
                "latency_ms": 128,
                "token_usage": {"prompt": 10, "completion": 5},
                "artifacts": [{"id": "artifact-1"}],
                "prompts": ["contact user@example.com secret=abc12345"],
                "responses": {"text": "Completed."},
                "messages": [
                    {"role": "assistant", "content": "Hello world"},
                    "plain response",
                ],
                "status": "completed",
                "completed_at": (
                    first_step_at + timedelta(milliseconds=500)
                ).isoformat(),
            }
        },
        at=first_step_at,
    )
    record.append_step(
        {
            "validator": {
                "id": "node-2",
                "display_name": "Validator",
                "status": "error",
                "error": {"message": "boom"},
            }
        },
        at=first_step_at + timedelta(seconds=1),
    )

    response = trace_to_response(record)

    assert response.execution.execution_id == "exec-test"
    assert response.execution.token_usage == {"input": 10, "output": 5}
    assert len(response.spans) == 3

    root_span = response.spans[0]
    assert root_span.status is not None
    assert root_span.status.model_dump() == {"code": "OK", "message": None}

    child = response.spans[1]
    assert child.attributes["orcheo.node.kind"] == "tool"
    assert child.attributes["orcheo.token.input"] == 10
    assert child.attributes["orcheo.artifact.ids"] == ["artifact-1"]
    prompt_event = next(event for event in child.events if event.name == "prompt")
    assert prompt_event.attributes["preview"].startswith("contact")
    message_event = next(event for event in child.events if event.name == "message")
    assert message_event.attributes["role"] == "assistant"

    error_child = response.spans[2]
    assert error_child.status is not None
    assert error_child.status.model_dump() == {"code": "ERROR", "message": "boom"}


def test_trace_update_from_step_includes_root_when_complete() -> None:
    """trace_update_from_step should emit root span when completing."""

    record = _base_record(status="cancelled")
    record.error = "cancelled"
    update = trace_update_from_step(
        record=record,
        step=None,
        complete=True,
    )
    assert update is not None
    assert len(update.spans) == 1
    assert update.spans[0].status is not None
    assert update.spans[0].status.model_dump() == {
        "code": "ERROR",
        "message": "cancelled",
    }


def test_trace_update_from_step_returns_none_for_non_span_payload() -> None:
    """Non-mapping steps should not generate trace updates when incomplete."""

    record = _base_record()
    empty_step = RunHistoryStep(
        index=0, at=record.trace_started_at, payload={"status": "completed"}
    )
    update = trace_update_from_step(record=record, step=empty_step, complete=False)
    assert update is None
