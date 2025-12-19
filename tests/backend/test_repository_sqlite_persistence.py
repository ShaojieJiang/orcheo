"""Tests for SQLite persistence helpers."""

from __future__ import annotations
from collections.abc import Mapping
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4
import pytest
from orcheo.models.workflow import WorkflowVersion
from orcheo_backend.app.repository_sqlite._persistence import SqlitePersistenceMixin


class _DummyPersistence(SqlitePersistenceMixin):
    def __init__(self, version: WorkflowVersion) -> None:
        super().__init__(database_path=":memory:")
        self._version = version
        self._connection_obj = SimpleNamespace(execute=AsyncMock())
        self._trigger_layer = SimpleNamespace(
            track_run=Mock(),
            register_cron_run=Mock(),
        )

    async def _get_version_locked(self, version_id: UUID) -> WorkflowVersion:
        return self._version

    @asynccontextmanager
    async def _connection(self) -> Any:
        yield self._connection_obj


class _FakeConfig:
    def model_dump(self, *, mode: str) -> dict[str, Any]:
        return {
            "tags": ["alpha"],
            "callbacks": ["cb"],
            "metadata": {"stage": "test"},
            "run_name": "custom-run",
        }


class _MappingConfig(Mapping[str, object]):
    def __init__(self, data: dict[str, object]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> object:
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


def _workflow_version(workflow_id: UUID) -> WorkflowVersion:
    return WorkflowVersion(
        workflow_id=workflow_id,
        version=1,
        graph={},
        metadata={},
        created_by="tester",
    )


@pytest.mark.asyncio
async def test_create_run_locked_tracks_config_and_cron() -> None:
    workflow_id = uuid4()
    persistence = _DummyPersistence(_workflow_version(workflow_id))
    config = _FakeConfig()
    run = await persistence._create_run_locked(
        workflow_id=workflow_id,
        workflow_version_id=uuid4(),
        triggered_by="cron",
        input_payload={"input": 1},
        actor=None,
        runnable_config=config,
    )

    assert run.tags == ["alpha"]
    assert run.callbacks == ["cb"]
    assert run.metadata == {"stage": "test"}
    assert run.run_name == "custom-run"
    persistence._trigger_layer.track_run.assert_called_once_with(workflow_id, run.id)
    persistence._trigger_layer.register_cron_run.assert_called_once_with(run.id)


@pytest.mark.asyncio
async def test_create_run_locked_accepts_mapping_config() -> None:
    workflow_id = uuid4()
    persistence = _DummyPersistence(_workflow_version(workflow_id))
    mapping_config = {
        "tags": ["beta"],
        "callbacks": [],
        "metadata": {"stage": "map"},
        "run_name": "map-run",
    }
    run = await persistence._create_run_locked(
        workflow_id=workflow_id,
        workflow_version_id=uuid4(),
        triggered_by="manual",
        input_payload={"input": 2},
        actor="actor",
        runnable_config=mapping_config,
    )

    assert run.tags == ["beta"]
    assert run.callbacks == []
    assert run.metadata == {"stage": "map"}
    assert run.run_name == "map-run"
    persistence._trigger_layer.register_cron_run.assert_not_called()


@pytest.mark.asyncio
async def test_create_run_locked_accepts_mapping_subclass() -> None:
    workflow_id = uuid4()
    persistence = _DummyPersistence(_workflow_version(workflow_id))
    mapping_config = _MappingConfig(
        {
            "tags": ["gamma"],
            "callbacks": ["cb"],
            "metadata": {"stage": "map"},
            "run_name": "map-run",
        }
    )
    run = await persistence._create_run_locked(
        workflow_id=workflow_id,
        workflow_version_id=uuid4(),
        triggered_by="manual",
        input_payload={},
        actor="user",
        runnable_config=mapping_config,
    )

    assert run.tags == ["gamma"]
    assert run.callbacks == ["cb"]
    assert run.metadata == {"stage": "map"}
    assert run.run_name == "map-run"
