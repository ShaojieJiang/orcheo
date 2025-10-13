"""Tests for the in-memory execution history store."""

from __future__ import annotations
import pytest
from orcheo_backend.app.history import (
    InMemoryRunHistoryStore,
    RunHistoryError,
    RunHistoryNotFoundError,
    RunHistoryRecord,
)


def test_run_history_record_mark_failed_sets_error() -> None:
    """Marking a record as failed updates status, timestamp, and error."""

    record = RunHistoryRecord(workflow_id="wf", execution_id="exec")
    record.mark_failed("boom")

    assert record.status == "error"
    assert record.error == "boom"
    assert record.completed_at is not None


def test_run_history_record_mark_cancelled_sets_status() -> None:
    """Marking a record as cancelled updates status and timestamp."""

    record = RunHistoryRecord(workflow_id="wf", execution_id="exec")
    record.mark_cancelled(reason="shutdown")

    assert record.status == "cancelled"
    assert record.error == "shutdown"
    assert record.completed_at is not None


@pytest.mark.asyncio
async def test_start_run_duplicate_execution_id_raises() -> None:
    """Starting the same execution twice surfaces a descriptive error."""

    store = InMemoryRunHistoryStore()
    await store.start_run(workflow_id="wf", execution_id="exec")

    with pytest.raises(RunHistoryError, match="execution_id=exec"):
        await store.start_run(workflow_id="wf", execution_id="exec")


@pytest.mark.asyncio
async def test_mark_failed_returns_copy_and_persists() -> None:
    """Marking a run as failed stores the status change and returns a copy."""

    store = InMemoryRunHistoryStore()
    await store.start_run(workflow_id="wf", execution_id="exec")

    result = await store.mark_failed("exec", "boom")
    assert result.status == "error"
    assert result.error == "boom"

    history = await store.get_history("exec")
    assert history.status == "error"
    assert history.error == "boom"


@pytest.mark.asyncio
async def test_mark_cancelled_returns_copy_and_persists() -> None:
    """Marking a run as cancelled stores the status change and returns a copy."""

    store = InMemoryRunHistoryStore()
    await store.start_run(workflow_id="wf", execution_id="exec")

    result = await store.mark_cancelled("exec", reason="cancelled")
    assert result.status == "cancelled"
    assert result.error == "cancelled"

    history = await store.get_history("exec")
    assert history.status == "cancelled"
    assert history.error == "cancelled"


@pytest.mark.asyncio
async def test_missing_history_raises_not_found() -> None:
    """Accessing an unknown execution raises the not-found error."""

    store = InMemoryRunHistoryStore()

    with pytest.raises(RunHistoryNotFoundError):
        await store.get_history("missing")


@pytest.mark.asyncio
async def test_clear_removes_all_histories() -> None:
    """Clearing the store wipes tracked executions."""

    store = InMemoryRunHistoryStore()
    await store.start_run(workflow_id="wf", execution_id="exec")

    await store.clear()

    with pytest.raises(RunHistoryNotFoundError):
        await store.get_history("exec")
