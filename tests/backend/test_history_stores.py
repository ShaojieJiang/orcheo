"""Tests for backend run history stores."""

from __future__ import annotations
from pathlib import Path
import pytest
from orcheo_backend.app.history import InMemoryRunHistoryStore
from orcheo_backend.app.history.sqlite_store import SqliteRunHistoryStore


class _ModelDumpConfig:
    """Minimal config-like object that supports `model_dump`."""

    def __init__(self) -> None:
        self._payload = {
            "tags": ["alpha"],
            "callbacks": ["cb"],
            "metadata": {"trace": "data"},
            "run_name": "model-dump-run",
        }

    def model_dump(self, mode: str) -> dict[str, object]:
        assert mode == "json"
        return self._payload


@pytest.mark.asyncio
async def test_inmemory_run_history_uses_model_dump_config() -> None:
    store = InMemoryRunHistoryStore()
    config = _ModelDumpConfig()

    record = await store.start_run(
        workflow_id="wf-model",
        execution_id="exec-model",
        runnable_config=config,
    )

    assert record.tags == config._payload["tags"]
    assert record.callbacks == config._payload["callbacks"]
    assert record.metadata == config._payload["metadata"]
    assert record.run_name == config._payload["run_name"]


@pytest.mark.asyncio
async def test_sqlite_run_history_uses_model_dump_config(tmp_path: Path) -> None:
    store = SqliteRunHistoryStore(tmp_path / "history.sqlite")
    config = _ModelDumpConfig()

    record = await store.start_run(
        workflow_id="wf-model-sql",
        execution_id="exec-model-sql",
        runnable_config=config,
    )

    assert record.tags == config._payload["tags"]
    assert record.callbacks == config._payload["callbacks"]
    assert record.metadata == config._payload["metadata"]
    assert record.run_name == config._payload["run_name"]
