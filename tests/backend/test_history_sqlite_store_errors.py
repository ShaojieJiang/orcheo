"""SQLite run history store error-handling and concurrency tests."""

from __future__ import annotations
import asyncio
from pathlib import Path
import pytest
from orcheo_backend.app.history import (
    RunHistoryNotFoundError,
    SqliteRunHistoryStore,
)


@pytest.mark.asyncio
async def test_sqlite_store_mark_failed_missing_execution_raises(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "history-fail-missing.sqlite"
    store = SqliteRunHistoryStore(str(db_path))

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.mark_failed("missing", "error")


@pytest.mark.asyncio
async def test_sqlite_store_mark_cancelled_missing_execution_raises(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "history-cancel-missing.sqlite"
    store = SqliteRunHistoryStore(str(db_path))

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.mark_cancelled("missing", reason="cancelled")


@pytest.mark.asyncio
async def test_sqlite_store_mark_completed_missing_execution_raises(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "history-complete-missing.sqlite"
    store = SqliteRunHistoryStore(str(db_path))

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.mark_completed("missing")


@pytest.mark.asyncio
async def test_sqlite_store_get_history_missing_raises(tmp_path: Path) -> None:
    db_path = tmp_path / "history-get-missing.sqlite"
    store = SqliteRunHistoryStore(str(db_path))

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.get_history("missing")


@pytest.mark.asyncio
async def test_sqlite_store_clear_removes_all(tmp_path: Path) -> None:
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
    db_path = tmp_path / "history-init.sqlite"
    store = SqliteRunHistoryStore(str(db_path))

    await store.start_run(workflow_id="wf1", execution_id="exec1")
    await store.start_run(workflow_id="wf2", execution_id="exec2")

    history1 = await store.get_history("exec1")
    history2 = await store.get_history("exec2")
    assert history1.workflow_id == "wf1"
    assert history2.workflow_id == "wf2"


@pytest.mark.asyncio
async def test_sqlite_store_concurrent_initialization(tmp_path: Path) -> None:
    db_path = tmp_path / "history-concurrent.sqlite"
    store = SqliteRunHistoryStore(str(db_path))

    async def start_run_task(exec_id: str) -> None:
        await store.start_run(workflow_id="wf", execution_id=exec_id)

    tasks = [start_run_task(f"exec{i}") for i in range(5)]
    await asyncio.gather(*tasks)

    for i in range(5):
        history = await store.get_history(f"exec{i}")
        assert history.workflow_id == "wf"
