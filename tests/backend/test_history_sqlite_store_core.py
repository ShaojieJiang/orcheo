"""Core SQLite run history store tests covering CRUD flows."""

from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
import pytest
from orcheo_backend.app.history import (
    RunHistoryError,
    RunHistoryNotFoundError,
    SqliteRunHistoryStore,
)


@pytest.mark.asyncio
async def test_sqlite_store_persists_history(tmp_path: Path) -> None:
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
    assert history.trace_started_at is not None

    store_reloaded = SqliteRunHistoryStore(str(db_path))
    persisted = await store_reloaded.get_history("exec")
    assert persisted.status == "completed"
    assert persisted.steps[0].payload == {"status": "running"}


@pytest.mark.asyncio
async def test_sqlite_store_duplicate_execution_id_raises(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "history-dupe.sqlite"
    store = SqliteRunHistoryStore(str(db_path))
    await store.start_run(workflow_id="wf", execution_id="exec")

    with pytest.raises(RunHistoryError, match="execution_id=exec"):
        await store.start_run(workflow_id="wf", execution_id="exec")


@pytest.mark.asyncio
async def test_sqlite_store_append_step_missing_execution_raises(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "history-append.sqlite"
    store = SqliteRunHistoryStore(str(db_path))

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.append_step("missing", {"action": "start"})


@pytest.mark.asyncio
async def test_sqlite_list_histories_filters_by_workflow(tmp_path: Path) -> None:
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
    db_path = tmp_path / "history-complete.sqlite"
    store = SqliteRunHistoryStore(str(db_path))
    await store.start_run(workflow_id="wf", execution_id="exec")

    result = await store.mark_completed("exec")
    assert result.status == "completed"
    assert result.completed_at is not None
    assert result.error is None
    assert result.trace_completed_at == result.completed_at

    history = await store.get_history("exec")
    assert history.status == "completed"
    assert history.trace_completed_at == history.completed_at


@pytest.mark.asyncio
async def test_sqlite_store_mark_failed(tmp_path: Path) -> None:
    db_path = tmp_path / "history-failed.sqlite"
    store = SqliteRunHistoryStore(str(db_path))
    await store.start_run(workflow_id="wf", execution_id="exec")

    result = await store.mark_failed("exec", "boom")
    assert result.status == "error"
    assert result.error == "boom"
    assert result.completed_at is not None
    assert result.trace_completed_at == result.completed_at

    history = await store.get_history("exec")
    assert history.status == "error"
    assert history.error == "boom"
    assert history.trace_completed_at == history.completed_at


@pytest.mark.asyncio
async def test_sqlite_store_mark_cancelled(tmp_path: Path) -> None:
    db_path = tmp_path / "history-cancelled.sqlite"
    store = SqliteRunHistoryStore(str(db_path))
    await store.start_run(workflow_id="wf", execution_id="exec")

    result = await store.mark_cancelled("exec", reason="shutdown")
    assert result.status == "cancelled"
    assert result.error == "shutdown"
    assert result.completed_at is not None
    assert result.trace_completed_at == result.completed_at

    history = await store.get_history("exec")
    assert history.status == "cancelled"
    assert history.error == "shutdown"
    assert history.trace_completed_at == history.completed_at


@pytest.mark.asyncio
async def test_sqlite_store_records_trace_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "history-trace.sqlite"
    store = SqliteRunHistoryStore(str(db_path))
    trace_started = datetime.now(tz=UTC)

    await store.start_run(
        workflow_id="wf",
        execution_id="exec",
        trace_id="trace-abc",
        root_span_id="root-def",
        trace_started_at=trace_started,
    )
    await store.mark_completed("exec")

    history = await store.get_history("exec")
    assert history.trace_id == "trace-abc"
    assert history.root_span_id == "root-def"
    assert history.trace_started_at == trace_started
    assert history.trace_completed_at is not None
