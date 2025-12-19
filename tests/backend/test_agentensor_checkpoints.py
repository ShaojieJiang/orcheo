"""Tests for Agentensor checkpoint persistence backends."""

from __future__ import annotations
import asyncio
from pathlib import Path
import pytest
from pydantic import ValidationError
from orcheo.agentensor.checkpoints import (
    AgentensorCheckpoint,
    AgentensorCheckpointNotFoundError,
)
from orcheo_backend.app.agentensor import checkpoint_store as checkpoint_store_module
from orcheo_backend.app.agentensor.checkpoint_store import (
    InMemoryAgentensorCheckpointStore,
    SqliteAgentensorCheckpointStore,
)
from orcheo_backend.app.history.sqlite_utils import connect_sqlite


class _RollbackRecordingConnection:
    def __init__(self, rollback_calls: list[str]) -> None:
        self._rollback_calls = rollback_calls

    async def execute(
        self, query: str, params: tuple[object, ...] | None = None
    ) -> _RollbackRecordingConnection:
        if "INSERT INTO agentensor_checkpoints" in query:
            raise RuntimeError("boom")
        return self

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        self._rollback_calls.append("rollback")

    async def __aenter__(self) -> _RollbackRecordingConnection:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        return None

    async def fetchone(self) -> dict[str, int] | None:
        return {"max_version": 0}


class _RollbackConnectionManager:
    def __init__(self, connection: _RollbackRecordingConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> _RollbackRecordingConnection:
        return self._connection

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        return None


async def _no_op_schema(_: Path) -> None:
    return None


@pytest.mark.asyncio
async def test_inmemory_checkpoint_store_increments_versions() -> None:
    store = InMemoryAgentensorCheckpointStore()

    first = await store.record_checkpoint(
        workflow_id="wf-1",
        runnable_config={"a": 1},
        metrics={"score": 0.1},
        is_best=False,
    )
    second = await store.record_checkpoint(
        workflow_id="wf-1",
        runnable_config={"a": 2},
        metrics={"score": 0.9},
        is_best=True,
    )

    assert {first.config_version, second.config_version} == {1, 2}
    assert second.is_best is True
    assert first.is_best is False
    latest = await store.latest_checkpoint("wf-1")
    assert latest is second
    listed = await store.list_checkpoints("wf-1")
    assert listed[0] is second
    assert listed[1] is first


def test_checkpoint_model_validates_fields() -> None:
    with pytest.raises(ValidationError):
        AgentensorCheckpoint(
            workflow_id="",
            config_version=0,
            runnable_config={},
            metrics={},
            metadata={},
        )

    checkpoint = AgentensorCheckpoint(
        workflow_id="wf-valid",
        config_version=1,
        runnable_config={},
        metrics={},
        metadata={},
    )

    assert checkpoint.workflow_id == "wf-valid"


@pytest.mark.asyncio
async def test_inmemory_checkpoint_store_handles_concurrent_writes() -> None:
    store = InMemoryAgentensorCheckpointStore()

    cp1, cp2 = await asyncio.gather(
        store.record_checkpoint(
            workflow_id="wf-cc",
            runnable_config={},
            metrics={},
        ),
        store.record_checkpoint(
            workflow_id="wf-cc",
            runnable_config={},
            metrics={},
        ),
    )

    assert {cp1.config_version, cp2.config_version} == {1, 2}


@pytest.mark.asyncio
async def test_sqlite_checkpoint_store_persists_and_retrieves(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "agentensor.sqlite"
    store = SqliteAgentensorCheckpointStore(store_path)

    first = await store.record_checkpoint(
        workflow_id="wf-2",
        runnable_config={"p": "v1"},
        metrics={"score": 0.3},
    )
    best = await store.record_checkpoint(
        workflow_id="wf-2",
        runnable_config={"p": "v2"},
        metrics={"score": 0.8},
        is_best=True,
    )

    assert best.is_best is True
    assert best.config_version == first.config_version + 1
    listed = await store.list_checkpoints("wf-2")
    assert listed[0].id == best.id
    fetched = await store.get_checkpoint(first.id)
    assert fetched.runnable_config == {"p": "v1"}
    with pytest.raises(AgentensorCheckpointNotFoundError):
        await store.get_checkpoint("missing")


@pytest.mark.asyncio
async def test_sqlite_checkpoint_store_resets_previous_best(tmp_path: Path) -> None:
    store_path = tmp_path / "agentensor.sqlite"
    store = SqliteAgentensorCheckpointStore(store_path)

    await store.record_checkpoint(
        workflow_id="wf-3",
        runnable_config={"p": "v1"},
        metrics={"score": 0.4},
        is_best=True,
    )
    second = await store.record_checkpoint(
        workflow_id="wf-3",
        runnable_config={"p": "v2"},
        metrics={"score": 0.9},
        is_best=True,
    )

    listed = await store.list_checkpoints("wf-3")
    assert second.id == listed[0].id
    assert sum(1 for cp in listed if cp.is_best) == 1
    assert all(cp.is_best is (cp.id == second.id) for cp in listed)


@pytest.mark.asyncio
async def test_inmemory_checkpoint_store_limit_and_missing() -> None:
    store = InMemoryAgentensorCheckpointStore()

    await store.record_checkpoint(
        workflow_id="wf-limit",
        runnable_config={},
        metrics={},
    )
    second = await store.record_checkpoint(
        workflow_id="wf-limit",
        runnable_config={},
        metrics={},
    )

    limited = await store.list_checkpoints("wf-limit", limit=1)
    assert limited == [second]

    with pytest.raises(AgentensorCheckpointNotFoundError):
        await store.get_checkpoint("missing")

    assert await store.latest_checkpoint("missing-workflow") is None


@pytest.mark.asyncio
async def test_inmemory_checkpoint_store_gets_existing_checkpoint() -> None:
    store = InMemoryAgentensorCheckpointStore()

    checkpoint = await store.record_checkpoint(
        workflow_id="wf-get",
        runnable_config={"foo": "value"},
        metrics={"score": 0.5},
    )

    assert await store.get_checkpoint(checkpoint.id) is checkpoint


@pytest.mark.asyncio
async def test_sqlite_checkpoint_store_limit_and_version(tmp_path: Path) -> None:
    store_path = tmp_path / "agentensor.sqlite"
    store = SqliteAgentensorCheckpointStore(store_path)

    await store.record_checkpoint(
        workflow_id="wf-limit",
        runnable_config={},
        metrics={},
        config_version=5,
    )
    await store.record_checkpoint(
        workflow_id="wf-limit",
        runnable_config={},
        metrics={},
    )

    limited = await store.list_checkpoints("wf-limit", limit=1)
    assert len(limited) == 1
    assert limited[0].config_version == 6

    latest = await store.latest_checkpoint("wf-limit")
    assert latest is not None

    assert await store.latest_checkpoint("empty") is None

    await store._ensure_initialized()
    async with connect_sqlite(store_path) as conn:
        provided = await store._resolve_version(conn, "wf-limit", provided_version=10)
        auto = await store._resolve_version(conn, "wf-limit", provided_version=None)

    assert provided == 10
    assert auto == 7


@pytest.mark.asyncio
async def test_sqlite_checkpoint_store_ensure_initialized_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_path = tmp_path / "agentensor.sqlite"
    store = SqliteAgentensorCheckpointStore(store_path)

    calls: list[str] = []

    async def fake_schema(path: Path) -> None:
        calls.append(str(path))

    monkeypatch.setattr(
        checkpoint_store_module,
        "ensure_sqlite_schema",
        fake_schema,
    )

    await store._ensure_initialized()
    await store._ensure_initialized()

    assert calls == [str(store_path)]


def test_inmemory_clear_other_best_handles_missing_checkpoint() -> None:
    store = InMemoryAgentensorCheckpointStore()
    store._by_workflow["wf-missing"] = ["ghost"]

    store._clear_other_best("wf-missing", "current")

    # ensure the missing identifier never raises and still preserves the mapping
    assert store._by_workflow["wf-missing"] == ["ghost"]


def test_inmemory_clear_other_best_resets_existing_best() -> None:
    # prepare a fake checkpoint that was previously marked best
    existing = AgentensorCheckpoint(
        workflow_id="wf-best",
        config_version=1,
        runnable_config={},
        metrics={},
        metadata={},
        is_best=True,
    )
    store = InMemoryAgentensorCheckpointStore()
    store._checkpoints[existing.id] = existing
    store._by_workflow["wf-best"] = [existing.id]

    store._clear_other_best("wf-best", "current")

    assert existing.is_best is False


@pytest.mark.asyncio
async def test_sqlite_checkpoint_store_rolls_back_on_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SqliteAgentensorCheckpointStore(tmp_path / "agentensor.sqlite")

    rollback_calls: list[str] = []

    def fake_connect(path: Path) -> _RollbackConnectionManager:
        return _RollbackConnectionManager(_RollbackRecordingConnection(rollback_calls))

    monkeypatch.setattr(
        checkpoint_store_module,
        "ensure_sqlite_schema",
        _no_op_schema,
    )
    monkeypatch.setattr(
        checkpoint_store_module,
        "connect_sqlite",
        fake_connect,
    )

    with pytest.raises(RuntimeError):
        await store.record_checkpoint(
            workflow_id="wf-error",
            runnable_config={},
            metrics={},
        )

    assert rollback_calls == ["rollback"]


@pytest.mark.asyncio
async def test_sqlite_checkpoint_store_init_handles_concurrent_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SqliteAgentensorCheckpointStore(tmp_path / "agentensor.sqlite")
    first_started = asyncio.Event()
    continue_schema = asyncio.Event()
    paths: list[str] = []

    async def fake_schema(path: Path) -> None:
        paths.append(str(path))
        first_started.set()
        await continue_schema.wait()

    monkeypatch.setattr(
        checkpoint_store_module,
        "ensure_sqlite_schema",
        fake_schema,
    )

    async def run_first() -> None:
        await store._ensure_initialized()

    async def run_second() -> None:
        await store._ensure_initialized()

    task1 = asyncio.create_task(run_first())
    await first_started.wait()
    task2 = asyncio.create_task(run_second())
    await asyncio.sleep(0)
    continue_schema.set()
    await asyncio.gather(task1, task2)

    assert paths == [str(store._database_path)]
