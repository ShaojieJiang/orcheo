from __future__ import annotations

from datetime import UTC, datetime

from orcheo_backend.app.history import RunHistoryRecord, RunHistoryStep
from orcheo_backend.app.history_utils import (
    trace_completion_message,
    trace_to_response,
    trace_update_message,
)


def _build_history_record() -> RunHistoryRecord:
    started_at = datetime.now(tz=UTC)
    record = RunHistoryRecord(
        workflow_id="wf-1",
        execution_id="exec-1",
        inputs={"foo": "bar"},
        status="completed",
        started_at=started_at,
        steps=[],
        trace_id="trace-123",
        trace_started_at=started_at,
        trace_completed_at=started_at,
        trace_last_span_at=started_at,
    )
    record.steps = [
        RunHistoryStep(
            index=0,
            at=started_at,
            payload={
                "node-1": {
                    "id": "node-1",
                    "display_name": "Draft",
                    "status": "success",
                    "token_usage": {"input": 1500, "output": 200},
                    "prompts": ["hello"],
                    "responses": ["hi"],
                    "messages": [
                        {"role": "user", "content": "greeting"},
                        "fallback",
                    ],
                    "artifacts": [{"id": "artifact-1"}],
                }
            },
        ),
        RunHistoryStep(
            index=1,
            at=started_at,
            payload={
                "node-2": {
                    "id": "node-2",
                    "status": "error",
                    "error": {"message": "something failed"},
                    "token_usage": {"input": 5, "output": 0},
                }
            },
        ),
    ]
    return record


def test_trace_to_response_includes_spans_and_usage() -> None:
    record = _build_history_record()

    response = trace_to_response(record)

    assert response.execution.id == "exec-1"
    assert response.execution.trace_id == "trace-123"
    assert response.execution.token_usage is not None
    assert response.execution.token_usage.model_dump() == {
        "input": 1505,
        "output": 200,
    }
    assert response.page_info.has_next_page is False
    assert len(response.spans) == 3
    root = response.spans[0]
    assert root.parent_span_id is None
    child_names = {span.name for span in response.spans[1:]}
    assert {"Draft", "node-2"} <= child_names
    draft_span = next(span for span in response.spans if span.name == "Draft")
    event_names = {event.name for event in draft_span.events}
    assert {"prompt", "response", "message", "token.chunk"} <= event_names


def test_trace_to_response_paginates_steps() -> None:
    record = _build_history_record()

    response = trace_to_response(record, cursor=1, limit=1)

    assert len(response.spans) == 1
    assert response.page_info.has_next_page is False
    assert response.page_info.cursor == 2
    assert response.spans[0].name == "node-2"


def test_trace_update_message_includes_root_and_cursor() -> None:
    record = _build_history_record()
    message = trace_update_message(
        execution_id=record.execution_id,
        workflow_id=record.workflow_id,
        trace_id=record.trace_id,
        trace_started_at=record.trace_started_at or record.started_at,
        steps=[record.steps[0]],
        include_root=True,
        status="running",
    )

    assert message is not None
    assert message.spans[0].parent_span_id is None
    assert any(span.name == "Draft" for span in message.spans[1:])
    assert message.cursor == 1
    assert message.complete is False


def test_trace_update_message_omits_when_empty() -> None:
    record = _build_history_record()

    message = trace_update_message(
        execution_id=record.execution_id,
        workflow_id=record.workflow_id,
        trace_id=record.trace_id,
        trace_started_at=record.trace_started_at or record.started_at,
        steps=(),
        include_root=False,
    )

    assert message is None


def test_trace_completion_message_marks_complete() -> None:
    record = _build_history_record()

    message = trace_completion_message(record)

    assert message is not None
    assert message.complete is True
    assert message.cursor == len(record.steps)
    assert message.spans[0].status.code in {"OK", "ERROR", "UNSET"}
