"""Tests for the persistence helper utilities."""

from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock
import pytest
from dynaconf import Dynaconf
from orcheo import config, persistence
from orcheo.persistence import create_checkpointer


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

    saver_mock = MagicMock(side_effect=lambda conn: ("pg_saver", conn))
    monkeypatch.setattr("orcheo.persistence.AsyncPostgresSaver", saver_mock)

    async with create_checkpointer(settings) as checkpointer:
        assert checkpointer == ("pg_saver", "pg_connection")

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
