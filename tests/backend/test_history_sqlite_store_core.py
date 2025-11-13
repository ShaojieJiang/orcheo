"""Core SQLite run history store tests covering CRUD flows."""

from __future__ import annotations
from pathlib import Path
from datetime import UTC, datetime

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

    history = await store.get_history("exec")
    assert history.status == "completed"


@pytest.mark.asyncio
async def test_sqlite_store_mark_failed(tmp_path: Path) -> None:
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
async def test_sqlite_store_update_trace_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "history-trace.sqlite"
    store = SqliteRunHistoryStore(str(db_path))
    await store.start_run(workflow_id="wf", execution_id="exec")

    started_at = datetime.now(tz=UTC)
    updated_at = started_at.replace(microsecond=0)

    result = await store.update_trace_metadata(
        "exec",
        trace_id="trace-1",
        started_at=started_at,
        updated_at=updated_at,
    )

    assert result.trace_id == "trace-1"
    assert result.trace_started_at == started_at
    assert result.trace_updated_at == updated_at

    fetched = await store.get_history("exec")
    assert fetched.trace_id == "trace-1"
