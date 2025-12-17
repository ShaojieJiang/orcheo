"""Tests for Agentensor checkpoint persistence backends."""

from __future__ import annotations
import asyncio
from pathlib import Path
import pytest
from orcheo.agentensor.checkpoints import AgentensorCheckpointNotFoundError
from orcheo_backend.app.agentensor.checkpoint_store import (
    InMemoryAgentensorCheckpointStore,
    SqliteAgentensorCheckpointStore,
)


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
