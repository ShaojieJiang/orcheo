"""Tests for the persistence helper utilities."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock
import pytest
from dynaconf import Dynaconf
from orcheo import config, persistence
from orcheo.persistence import create_checkpointer, create_graph_store


@pytest.mark.asyncio
async def test_create_checkpointer_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    """SQLite backend should yield a saver created from the configured path."""

    fake_conn = MagicMock()
    fake_conn.close = AsyncMock()

    monkeypatch.setattr(
        "orcheo.persistence.aiosqlite.connect", AsyncMock(return_value=fake_conn)
    )

    saver_mock = MagicMock(side_effect=lambda conn: ("sqlite_saver", conn))
    monkeypatch.setattr("orcheo.persistence.AsyncSqliteSaver", saver_mock)

    settings = config.get_settings(refresh=True)

    async with create_checkpointer(settings) as checkpointer:
        assert checkpointer == ("sqlite_saver", fake_conn)

    saver_mock.assert_called_once_with(fake_conn)
    fake_conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_checkpointer_sqlite_backfills_is_alive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ensure SQLite connection gets the is_alive shim LangGraph expects."""

    sqlite_file = tmp_path / "backfill.sqlite3"
    monkeypatch.setenv("ORCHEO_SQLITE_PATH", str(sqlite_file))

    fake_conn = MagicMock()
    fake_conn.close = AsyncMock()
    fake_conn._running = True
    fake_conn._connection = object()

    monkeypatch.setattr(
        "orcheo.persistence.aiosqlite.connect", AsyncMock(return_value=fake_conn)
    )
    monkeypatch.setattr("orcheo.persistence.AsyncSqliteSaver", MagicMock())

    settings = config.get_settings(refresh=True)

    async with create_checkpointer(settings):
        pass

    assert callable(fake_conn.is_alive)
    assert fake_conn.is_alive()


@pytest.mark.asyncio
async def test_create_checkpointer_sqlite_creates_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SQLite backend should ensure the target directory exists before connecting."""

    target_dir = tmp_path / "nested"
    sqlite_file = target_dir / "orcheo.sqlite3"

    monkeypatch.setenv("ORCHEO_CHECKPOINT_BACKEND", "sqlite")
    monkeypatch.setenv("ORCHEO_SQLITE_PATH", str(sqlite_file))

    fake_conn = MagicMock()
    fake_conn.close = AsyncMock()

    connect_mock = AsyncMock(return_value=fake_conn)
    monkeypatch.setattr("orcheo.persistence.aiosqlite.connect", connect_mock)
    monkeypatch.setattr("orcheo.persistence.AsyncSqliteSaver", MagicMock())

    settings = config.get_settings(refresh=True)

    assert not target_dir.exists()

    async with create_checkpointer(settings):
        pass

    assert target_dir.exists()
    connect_mock.assert_awaited_once_with(str(sqlite_file))
    fake_conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_checkpointer_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    """Postgres backend should open a pooled connection and close it afterwards."""

    monkeypatch.setenv("ORCHEO_CHECKPOINT_BACKEND", "postgres")
    monkeypatch.setenv("ORCHEO_POSTGRES_DSN", "postgresql://example")

    settings = config.get_settings(refresh=True)

    fake_pool = MagicMock()
    fake_pool.open = AsyncMock()
    fake_conn_cm = AsyncMock()
    fake_conn_cm.__aenter__.return_value = "pg_connection"
    fake_conn_cm.__aexit__.return_value = None
    fake_pool.connection.return_value = fake_conn_cm
    fake_pool.close = AsyncMock()

    monkeypatch.setattr(
        "orcheo.persistence.AsyncConnectionPool", MagicMock(return_value=fake_pool)
    )
    if persistence.DictRowFactory is None:
        monkeypatch.setattr("orcheo.persistence.DictRowFactory", MagicMock())

    fake_saver = MagicMock()
    fake_saver.setup = AsyncMock()
    saver_class = MagicMock(return_value=fake_saver)
    monkeypatch.setattr("orcheo.persistence.AsyncPostgresSaver", saver_class)

    async with create_checkpointer(settings) as checkpointer:
        assert checkpointer is fake_saver

    saver_class.assert_called_once_with("pg_connection")
    fake_saver.setup.assert_awaited_once()
    fake_pool.connection.assert_called_once()
    fake_conn_cm.__aenter__.assert_awaited_once()
    fake_pool.open.assert_awaited_once()
    fake_pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_checkpointer_invalid_backend() -> None:
    """An unsupported backend should raise an error."""

    bad_settings = Dynaconf(
        envvar_prefix="ORCHEO", environments=False, load_dotenv=False, settings_files=[]
    )
    bad_settings.set("CHECKPOINT_BACKEND", cast(str, "invalid"))
    bad_settings.set("SQLITE_PATH", "irrelevant")
    bad_settings.set("POSTGRES_DSN", None)

    with pytest.raises(ValueError):
        async with create_checkpointer(bad_settings):
            raise AssertionError("context should not yield")


@pytest.mark.asyncio
async def test_create_graph_store_sqlite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SQLite graph-store backend should setup and yield the configured store."""

    sqlite_file = tmp_path / "graph_store.sqlite"
    monkeypatch.setenv("ORCHEO_GRAPH_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("ORCHEO_GRAPH_STORE_SQLITE_PATH", str(sqlite_file))

    fake_store = MagicMock()
    fake_store.setup = AsyncMock()
    calls: dict[str, str] = {}

    class StubSqliteStore:
        @classmethod
        @asynccontextmanager
        async def from_conn_string(cls, conn_string: str):
            calls["conn_string"] = conn_string
            yield fake_store

    monkeypatch.setattr("orcheo.persistence.AsyncSqliteStore", StubSqliteStore)

    settings = config.get_settings(refresh=True)
    async with create_graph_store(settings) as graph_store:
        assert graph_store is fake_store

    assert calls["conn_string"] == str(sqlite_file)
    fake_store.setup.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_graph_store_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    """Postgres graph-store backend should setup with pool config."""

    monkeypatch.setenv("ORCHEO_GRAPH_STORE_BACKEND", "postgres")
    monkeypatch.setenv("ORCHEO_POSTGRES_DSN", "postgresql://example")
    monkeypatch.setenv("ORCHEO_GRAPH_STORE_SQLITE_PATH", "/tmp/graph_store.sqlite")
    monkeypatch.setenv("ORCHEO_POSTGRES_POOL_MIN_SIZE", "2")
    monkeypatch.setenv("ORCHEO_POSTGRES_POOL_MAX_SIZE", "9")
    monkeypatch.setenv("ORCHEO_POSTGRES_POOL_TIMEOUT", "12")
    monkeypatch.setenv("ORCHEO_POSTGRES_POOL_MAX_IDLE", "60")

    fake_store = MagicMock()
    fake_store.setup = AsyncMock()
    calls: dict[str, object] = {}

    class StubPostgresStore:
        @classmethod
        @asynccontextmanager
        async def from_conn_string(
            cls,
            conn_string: str,
            *,
            pool_config: dict[str, object],
        ):
            calls["conn_string"] = conn_string
            calls["pool_config"] = pool_config
            yield fake_store

    monkeypatch.setattr("orcheo.persistence.AsyncPostgresStore", StubPostgresStore)

    settings = config.get_settings(refresh=True)
    async with create_graph_store(settings) as graph_store:
        assert graph_store is fake_store

    assert calls["conn_string"] == "postgresql://example"
    assert calls["pool_config"] == {
        "min_size": 2,
        "max_size": 9,
        "timeout": 12.0,
        "max_idle": 60.0,
    }
    fake_store.setup.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_graph_store_invalid_backend() -> None:
    """Unsupported graph-store backends should raise an error."""

    bad_settings = Dynaconf(
        envvar_prefix="ORCHEO", environments=False, load_dotenv=False, settings_files=[]
    )
    bad_settings.set("GRAPH_STORE_BACKEND", cast(str, "invalid"))
    bad_settings.set("GRAPH_STORE_SQLITE_PATH", "/tmp/irrelevant.sqlite")
    bad_settings.set("POSTGRES_DSN", None)

    with pytest.raises(ValueError):
        async with create_graph_store(bad_settings):
            raise AssertionError("context should not yield")
