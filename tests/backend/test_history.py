"""Tests for execution history stores."""

from __future__ import annotations
import asyncio
from pathlib import Path
import pytest
from orcheo_backend.app.history import (
    InMemoryRunHistoryStore,
    RunHistoryError,
    RunHistoryNotFoundError,
    RunHistoryRecord,
    SqliteRunHistoryStore,
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


def test_run_history_record_append_step_increments_index() -> None:
    """Appending a step auto-increments the index."""

    record = RunHistoryRecord(workflow_id="wf", execution_id="exec")
    step1 = record.append_step({"action": "start"})
    step2 = record.append_step({"action": "continue"})

    assert step1.index == 0
    assert step2.index == 1
    assert len(record.steps) == 2
    assert record.steps[0].payload == {"action": "start"}
    assert record.steps[1].payload == {"action": "continue"}


def test_run_history_record_mark_completed_clears_error() -> None:
    """Marking a record as completed clears any error and sets timestamp."""

    record = RunHistoryRecord(workflow_id="wf", execution_id="exec")
    record.error = "previous error"
    record.mark_completed()

    assert record.status == "completed"
    assert record.error is None
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


@pytest.mark.asyncio
async def test_in_memory_append_step_increments_index() -> None:
    """Appending steps to in-memory store auto-increments indices."""

    store = InMemoryRunHistoryStore()
    await store.start_run(workflow_id="wf", execution_id="exec")

    step1 = await store.append_step("exec", {"action": "start"})
    step2 = await store.append_step("exec", {"action": "continue"})

    assert step1.index == 0
    assert step2.index == 1

    history = await store.get_history("exec")
    assert len(history.steps) == 2
    assert history.steps[0].payload == {"action": "start"}
    assert history.steps[1].payload == {"action": "continue"}


@pytest.mark.asyncio
async def test_in_memory_append_step_missing_execution_raises() -> None:
    """Appending a step to unknown execution raises not-found error."""

    store = InMemoryRunHistoryStore()

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.append_step("missing", {"action": "start"})


@pytest.mark.asyncio
async def test_in_memory_mark_completed_persists_status() -> None:
    """Marking a run as completed stores the status change."""

    store = InMemoryRunHistoryStore()
    await store.start_run(workflow_id="wf", execution_id="exec")

    result = await store.mark_completed("exec")
    assert result.status == "completed"
    assert result.completed_at is not None
    assert result.error is None

    history = await store.get_history("exec")
    assert history.status == "completed"


@pytest.mark.asyncio
async def test_in_memory_mark_completed_missing_execution_raises() -> None:
    """Marking unknown execution as completed raises not-found error."""

    store = InMemoryRunHistoryStore()

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.mark_completed("missing")


@pytest.mark.asyncio
async def test_in_memory_mark_failed_missing_execution_raises() -> None:
    """Marking unknown execution as failed raises not-found error."""

    store = InMemoryRunHistoryStore()

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.mark_failed("missing", "error")


@pytest.mark.asyncio
async def test_in_memory_mark_cancelled_missing_execution_raises() -> None:
    """Marking unknown execution as cancelled raises not-found error."""

    store = InMemoryRunHistoryStore()

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.mark_cancelled("missing", reason="cancelled")


@pytest.mark.asyncio
async def test_in_memory_list_histories_filters_and_limits() -> None:
    """Listing histories returns records for the specified workflow."""

    store = InMemoryRunHistoryStore()
    await store.start_run(workflow_id="wf-a", execution_id="exec-1")
    await store.start_run(workflow_id="wf-b", execution_id="exec-2")

    records_all = await store.list_histories("wf-a")
    assert [record.execution_id for record in records_all] == ["exec-1"]

    records_limited = await store.list_histories("wf-a", limit=1)
    assert len(records_limited) == 1
    assert records_limited[0].execution_id == "exec-1"


@pytest.mark.asyncio
async def test_sqlite_store_persists_history(tmp_path: Path) -> None:
    """SQLite-backed store writes and retrieves execution metadata."""

    db_path = tmp_path / "history.sqlite"
    store = SqliteRunHistoryStore(str(db_path))
    await store.start_run(
        workflow_id="wf",
        execution_id="exec",
        inputs={"foo": "bar"},
    )
    await store.append_step("exec", {"status": "running"})
    await store.mark_completed("exec")

    history = await store.get_history("exec")
    assert history.status == "completed"
    assert history.inputs == {"foo": "bar"}
    assert len(history.steps) == 1
    assert history.steps[0].payload == {"status": "running"}

    # Reload via a new instance to confirm persistence
    store_reloaded = SqliteRunHistoryStore(str(db_path))
    persisted = await store_reloaded.get_history("exec")
    assert persisted.status == "completed"
    assert persisted.steps[0].payload == {"status": "running"}


@pytest.mark.asyncio
async def test_sqlite_store_duplicate_execution_id_raises(
    tmp_path: Path,
) -> None:
    """Duplicate execution identifiers surface a descriptive error."""

    db_path = tmp_path / "history-dupe.sqlite"
    store = SqliteRunHistoryStore(str(db_path))
    await store.start_run(workflow_id="wf", execution_id="exec")

    with pytest.raises(RunHistoryError, match="execution_id=exec"):
        await store.start_run(workflow_id="wf", execution_id="exec")


@pytest.mark.asyncio
async def test_sqlite_store_append_step_missing_execution_raises(
    tmp_path: Path,
) -> None:
    """Appending a step to unknown execution raises not-found error."""

    db_path = tmp_path / "history-append.sqlite"
    store = SqliteRunHistoryStore(str(db_path))

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.append_step("missing", {"action": "start"})


@pytest.mark.asyncio
async def test_sqlite_list_histories_filters_by_workflow(tmp_path: Path) -> None:
    """Listing histories from SQLite store scopes results by workflow."""

    db_path = tmp_path / "history-list.sqlite"
    store = SqliteRunHistoryStore(str(db_path))
    await store.start_run(workflow_id="wf-a", execution_id="exec-1")
    await store.start_run(workflow_id="wf-b", execution_id="exec-2")

    results = await store.list_histories("wf-a")
    assert [record.execution_id for record in results] == ["exec-1"]

    limited = await store.list_histories("wf-a", limit=1)
    assert len(limited) == 1
    assert limited[0].execution_id == "exec-1"


@pytest.mark.asyncio
async def test_sqlite_store_mark_completed(tmp_path: Path) -> None:
    """Marking a run as completed stores the status change."""

    db_path = tmp_path / "history-complete.sqlite"
    store = SqliteRunHistoryStore(str(db_path))
    await store.start_run(workflow_id="wf", execution_id="exec")

    result = await store.mark_completed("exec")
    assert result.status == "completed"
    assert result.completed_at is not None
    assert result.error is None

    history = await store.get_history("exec")
    assert history.status == "completed"


@pytest.mark.asyncio
async def test_sqlite_store_mark_failed(tmp_path: Path) -> None:
    """Marking a run as failed stores the error."""

    db_path = tmp_path / "history-failed.sqlite"
    store = SqliteRunHistoryStore(str(db_path))
    await store.start_run(workflow_id="wf", execution_id="exec")

    result = await store.mark_failed("exec", "boom")
    assert result.status == "error"
    assert result.error == "boom"
    assert result.completed_at is not None

    history = await store.get_history("exec")
    assert history.status == "error"
    assert history.error == "boom"


@pytest.mark.asyncio
async def test_sqlite_store_mark_cancelled(tmp_path: Path) -> None:
    """Marking a run as cancelled stores the reason."""

    db_path = tmp_path / "history-cancelled.sqlite"
    store = SqliteRunHistoryStore(str(db_path))
    await store.start_run(workflow_id="wf", execution_id="exec")

    result = await store.mark_cancelled("exec", reason="shutdown")
    assert result.status == "cancelled"
    assert result.error == "shutdown"
    assert result.completed_at is not None

    history = await store.get_history("exec")
    assert history.status == "cancelled"
    assert history.error == "shutdown"


@pytest.mark.asyncio
async def test_sqlite_store_mark_failed_missing_execution_raises(
    tmp_path: Path,
) -> None:
    """Marking unknown execution as failed raises not-found error."""

    db_path = tmp_path / "history-fail-missing.sqlite"
    store = SqliteRunHistoryStore(str(db_path))

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.mark_failed("missing", "error")


@pytest.mark.asyncio
async def test_sqlite_store_mark_cancelled_missing_execution_raises(
    tmp_path: Path,
) -> None:
    """Marking unknown execution as cancelled raises not-found error."""

    db_path = tmp_path / "history-cancel-missing.sqlite"
    store = SqliteRunHistoryStore(str(db_path))

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.mark_cancelled("missing", reason="cancelled")


@pytest.mark.asyncio
async def test_sqlite_store_mark_completed_missing_execution_raises(
    tmp_path: Path,
) -> None:
    """Marking unknown execution as completed raises not-found error."""

    db_path = tmp_path / "history-complete-missing.sqlite"
    store = SqliteRunHistoryStore(str(db_path))

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.mark_completed("missing")


@pytest.mark.asyncio
async def test_sqlite_store_get_history_missing_raises(tmp_path: Path) -> None:
    """Getting history for unknown execution raises not-found error."""

    db_path = tmp_path / "history-get-missing.sqlite"
    store = SqliteRunHistoryStore(str(db_path))

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.get_history("missing")


@pytest.mark.asyncio
async def test_sqlite_store_clear_removes_all(tmp_path: Path) -> None:
    """Clearing the store removes all histories and steps."""

    db_path = tmp_path / "history-clear.sqlite"
    store = SqliteRunHistoryStore(str(db_path))
    await store.start_run(workflow_id="wf1", execution_id="exec1")
    await store.append_step("exec1", {"action": "step1"})
    await store.start_run(workflow_id="wf2", execution_id="exec2")
    await store.append_step("exec2", {"action": "step2"})

    await store.clear()

    with pytest.raises(RunHistoryNotFoundError):
        await store.get_history("exec1")
    with pytest.raises(RunHistoryNotFoundError):
        await store.get_history("exec2")


@pytest.mark.asyncio
async def test_sqlite_store_initializes_once(tmp_path: Path) -> None:
    """Database initialization happens only once even with concurrent access."""

    db_path = tmp_path / "history-init.sqlite"
    store = SqliteRunHistoryStore(str(db_path))

    # First operation triggers initialization
    await store.start_run(workflow_id="wf1", execution_id="exec1")

    # Second operation should not re-initialize
    await store.start_run(workflow_id="wf2", execution_id="exec2")

    # Both records should exist
    history1 = await store.get_history("exec1")
    history2 = await store.get_history("exec2")
    assert history1.workflow_id == "wf1"
    assert history2.workflow_id == "wf2"


@pytest.mark.asyncio
async def test_sqlite_store_concurrent_initialization(tmp_path: Path) -> None:
    """Concurrent initialization is thread-safe and only initializes once."""

    db_path = tmp_path / "history-concurrent.sqlite"
    store = SqliteRunHistoryStore(str(db_path))

    # Trigger multiple concurrent initializations
    async def start_run_task(exec_id: str) -> None:
        await store.start_run(workflow_id="wf", execution_id=exec_id)

    # Launch multiple operations concurrently before initialization
    tasks = [start_run_task(f"exec{i}") for i in range(5)]
    await asyncio.gather(*tasks)

    # All executions should be stored
    for i in range(5):
        history = await store.get_history(f"exec{i}")
        assert history.workflow_id == "wf"
