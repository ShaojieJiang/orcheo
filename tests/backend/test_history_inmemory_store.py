"""Tests for the in-memory run history store implementation."""

from __future__ import annotations
from datetime import UTC, datetime
import pytest
from orcheo_backend.app.history import (
    InMemoryRunHistoryStore,
    RunHistoryError,
    RunHistoryNotFoundError,
)


@pytest.mark.asyncio
async def test_start_run_records_trace_metadata() -> None:
    store = InMemoryRunHistoryStore()
    started_at = datetime.now(tz=UTC)

    await store.start_run(
        workflow_id="wf",
        execution_id="exec",
        trace_id="trace-123",
        trace_started_at=started_at,
    )

    history = await store.get_history("exec")
    assert history.trace_id == "trace-123"
    assert history.trace_started_at == started_at
    assert history.trace_last_span_at == started_at
    assert history.trace_completed_at is None


@pytest.mark.asyncio
async def test_start_run_duplicate_execution_id_raises() -> None:
    store = InMemoryRunHistoryStore()
    await store.start_run(workflow_id="wf", execution_id="exec")

    with pytest.raises(RunHistoryError, match="execution_id=exec"):
        await store.start_run(workflow_id="wf", execution_id="exec")


@pytest.mark.asyncio
async def test_mark_failed_returns_copy_and_persists() -> None:
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
    store = InMemoryRunHistoryStore()

    with pytest.raises(RunHistoryNotFoundError):
        await store.get_history("missing")


@pytest.mark.asyncio
async def test_clear_removes_all_histories() -> None:
    store = InMemoryRunHistoryStore()
    await store.start_run(workflow_id="wf", execution_id="exec")

    await store.clear()

    with pytest.raises(RunHistoryNotFoundError):
        await store.get_history("exec")


@pytest.mark.asyncio
async def test_in_memory_append_step_increments_index() -> None:
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
    store = InMemoryRunHistoryStore()

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.append_step("missing", {"action": "start"})


@pytest.mark.asyncio
async def test_in_memory_mark_completed_persists_status() -> None:
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
    store = InMemoryRunHistoryStore()

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.mark_completed("missing")


@pytest.mark.asyncio
async def test_in_memory_mark_failed_missing_execution_raises() -> None:
    store = InMemoryRunHistoryStore()

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.mark_failed("missing", "error")


@pytest.mark.asyncio
async def test_in_memory_mark_cancelled_missing_execution_raises() -> None:
    store = InMemoryRunHistoryStore()

    with pytest.raises(RunHistoryNotFoundError, match="execution_id=missing"):
        await store.mark_cancelled("missing", reason="cancelled")


@pytest.mark.asyncio
async def test_in_memory_list_histories_filters_and_limits() -> None:
    store = InMemoryRunHistoryStore()
    await store.start_run(workflow_id="wf-a", execution_id="exec-1")
    await store.start_run(workflow_id="wf-b", execution_id="exec-2")

    records_all = await store.list_histories("wf-a")
    assert [record.execution_id for record in records_all] == ["exec-1"]

    records_limited = await store.list_histories("wf-a", limit=1)
    assert len(records_limited) == 1
    assert records_limited[0].execution_id == "exec-1"
