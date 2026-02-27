"""Persistence helpers that create LangGraph checkpoint savers and stores."""

from __future__ import annotations
import importlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast
import aiosqlite
from dynaconf import Dynaconf
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.sqlite.aio import AsyncSqliteStore
from orcheo.config import CheckpointBackend, GraphStoreBackend


AsyncPostgresSaver: Any | None
AsyncConnectionPool: Any | None
DictRowFactory: Any | None
AsyncPostgresStore: Any | None

try:  # pragma: no cover - optional dependency
    AsyncPostgresSaver = importlib.import_module(
        "langgraph.checkpoint.postgres.aio"
    ).AsyncPostgresSaver
    AsyncPostgresStore = importlib.import_module(
        "langgraph.store.postgres.aio"
    ).AsyncPostgresStore
    AsyncConnectionPool = importlib.import_module("psycopg_pool").AsyncConnectionPool
    DictRowFactory = importlib.import_module("psycopg.rows").dict_row
except Exception:  # pragma: no cover - fallback when dependency missing
    AsyncPostgresSaver = None
    AsyncPostgresStore = None
    AsyncConnectionPool = None
    DictRowFactory = None


def _ensure_sqlite_connection_is_alive(
    conn: aiosqlite.Connection,
) -> aiosqlite.Connection:
    """Backfill aiosqlite connections with the ``is_alive`` helper LangGraph expects."""
    if not hasattr(conn, "is_alive"):

        def _is_alive() -> bool:
            return bool(
                getattr(conn, "_running", False) and getattr(conn, "_connection", None)
            )

        conn.is_alive = _is_alive  # type: ignore[attr-defined]
    return conn


@asynccontextmanager
async def create_checkpointer(settings: Dynaconf) -> AsyncIterator[Any]:
    """Create a LangGraph checkpointer based on the configured backend."""
    backend = cast(CheckpointBackend, settings.checkpoint_backend)

    if backend == "sqlite":
        sqlite_path = Path(str(settings.sqlite_path)).expanduser()
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        conn = _ensure_sqlite_connection_is_alive(
            await aiosqlite.connect(str(sqlite_path))
        )
        try:
            yield AsyncSqliteSaver(conn)
        finally:
            await conn.close()
        return

    if backend == "postgres":
        if (
            AsyncPostgresSaver is None
            or AsyncConnectionPool is None
            or DictRowFactory is None
        ):  # pragma: no cover
            msg = (
                "Postgres backend requires psycopg_pool and langgraph postgres extras."
            )
            raise RuntimeError(msg)

        dsn = settings.postgres_dsn
        if dsn is None:  # pragma: no cover - defensive, validated earlier
            msg = "Postgres backend requires ORCHEO_POSTGRES_DSN to be set."
            raise RuntimeError(msg)

        pool = AsyncConnectionPool(
            dsn,
            open=False,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": DictRowFactory,
            },
        )
        await pool.open()
        try:
            async with pool.connection() as conn:  # type: ignore[attr-defined]
                checkpointer = AsyncPostgresSaver(cast(Any, conn))
                await checkpointer.setup()
                yield checkpointer
        finally:
            await pool.close()
        return

    msg = "Unsupported checkpoint backend configured."
    raise ValueError(msg)


@asynccontextmanager
async def create_graph_store(settings: Dynaconf) -> AsyncIterator[Any]:
    """Create a LangGraph store based on the configured backend."""
    backend = cast(GraphStoreBackend, settings.graph_store_backend)

    if backend == "sqlite":
        sqlite_path = Path(str(settings.graph_store_sqlite_path))
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        async with AsyncSqliteStore.from_conn_string(str(sqlite_path)) as store:
            await store.setup()
            yield store
        return

    if backend == "postgres":
        if AsyncPostgresStore is None:  # pragma: no cover
            msg = "Postgres graph store requires langgraph postgres extras."
            raise RuntimeError(msg)

        dsn = settings.postgres_dsn
        if dsn is None:  # pragma: no cover - defensive, validated earlier
            msg = "Postgres backend requires ORCHEO_POSTGRES_DSN to be set."
            raise RuntimeError(msg)

        pool_config = {
            "min_size": int(settings.postgres_pool_min_size),
            "max_size": int(settings.postgres_pool_max_size),
            "timeout": float(settings.postgres_pool_timeout),
            "max_idle": float(settings.postgres_pool_max_idle),
        }
        async with AsyncPostgresStore.from_conn_string(
            dsn,
            pool_config=pool_config,
        ) as store:
            await store.setup()
            yield store
        return

    msg = "Unsupported graph store backend configured."
    raise ValueError(msg)
