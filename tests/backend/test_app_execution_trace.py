import pytest
from datetime import UTC, datetime, timedelta
from fastapi import HTTPException

from orcheo_backend.app import get_execution_trace
from orcheo_backend.app.history import (
    RunHistoryNotFoundError,
    RunHistoryRecord,
    RunHistoryStep,
)


@pytest.mark.asyncio()
async def test_get_execution_trace_returns_spans() -> None:
    """Trace endpoint should return root and child span metadata."""

    started_at = datetime.now(tz=UTC)
    step_time = started_at + timedelta(seconds=1)

    record = RunHistoryRecord(
        workflow_id="wf-123",
        execution_id="exec-456",
        inputs={"foo": "bar"},
        status="completed",
        trace_id="trace-abc",
        trace_started_at=started_at,
        trace_completed_at=step_time,
        trace_last_span_at=step_time,
    )
    record.steps = [
        RunHistoryStep(
            index=0,
            at=step_time,
            payload={
                "node-1": {
                    "display_name": "LLM Node",
                    "status": "completed",
                    "token_usage": {"input": 5, "output": 7},
                    "artifacts": [{"id": "artifact-1"}],
                    "responses": ["response text"],
                }
            },
        )
    ]

    class HistoryStore:
        async def get_history(self, execution_id: str) -> RunHistoryRecord:
            assert execution_id == "exec-456"
            return record

    response = await get_execution_trace("exec-456", HistoryStore())

    assert response.execution.id == "exec-456"
    assert response.execution.trace_id == "trace-abc"
    assert response.execution.token_usage.input == 5
    assert response.execution.token_usage.output == 7
    assert response.execution.finished_at == step_time
    assert len(response.spans) == 2

    root = next(span for span in response.spans if span.parent_span_id is None)
    child = next(span for span in response.spans if span.parent_span_id == root.span_id)
    assert child.attributes["orcheo.node.display_name"] == "LLM Node"
    assert child.attributes["orcheo.artifact.ids"] == ["artifact-1"]
    assert any(event.name == "response" for event in child.events)


@pytest.mark.asyncio()
async def test_get_execution_trace_not_found() -> None:
    """Trace endpoint should surface 404 when history is missing."""

    class HistoryStore:
        async def get_history(self, execution_id: str) -> RunHistoryRecord:
            raise RunHistoryNotFoundError("missing")

    with pytest.raises(HTTPException) as exc_info:
        await get_execution_trace("missing", HistoryStore())

    assert exc_info.value.status_code == 404
