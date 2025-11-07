"""Unit tests for the RunHistoryRecord dataclass behavior."""

from __future__ import annotations
from orcheo_backend.app.history import RunHistoryRecord


def test_run_history_record_mark_failed_sets_error() -> None:
    record = RunHistoryRecord(workflow_id="wf", execution_id="exec")
    record.mark_failed("boom")

    assert record.status == "error"
    assert record.error == "boom"
    assert record.completed_at is not None


def test_run_history_record_mark_cancelled_sets_status() -> None:
    record = RunHistoryRecord(workflow_id="wf", execution_id="exec")
    record.mark_cancelled(reason="shutdown")

    assert record.status == "cancelled"
    assert record.error == "shutdown"
    assert record.completed_at is not None


def test_run_history_record_append_step_increments_index() -> None:
    record = RunHistoryRecord(workflow_id="wf", execution_id="exec")
    step1 = record.append_step({"action": "start"})
    step2 = record.append_step({"action": "continue"})

    assert step1.index == 0
    assert step2.index == 1
    assert len(record.steps) == 2
    assert record.steps[0].payload == {"action": "start"}
    assert record.steps[1].payload == {"action": "continue"}


def test_run_history_record_mark_completed_clears_error() -> None:
    record = RunHistoryRecord(workflow_id="wf", execution_id="exec")
    record.error = "previous error"
    record.mark_completed()

    assert record.status == "completed"
    assert record.error is None
    assert record.completed_at is not None
