"""Persistence helpers that create LangGraph checkpoint savers."""

from __future__ import annotations
import importlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from orcheo.config import Settings


AsyncPostgresSaver: Any | None
AsyncConnectionPool: Any | None

try:  # pragma: no cover - optional dependency
    AsyncPostgresSaver = importlib.import_module(
        "langgraph.checkpoint.postgres.aio"
    ).AsyncPostgresSaver
    AsyncConnectionPool = importlib.import_module("psycopg_pool").AsyncConnectionPool
except Exception:  # pragma: no cover - fallback when dependency missing
    AsyncPostgresSaver = None
    AsyncConnectionPool = None


@asynccontextmanager
async def create_checkpointer(settings: Settings) -> AsyncIterator[Any]:
    """Create a LangGraph checkpointer based on the configured backend."""
    persistence = settings.persistence

    if persistence.backend == "sqlite":
        conn = await aiosqlite.connect(persistence.sqlite_path)
        try:
            yield AsyncSqliteSaver(conn)
        finally:
            await conn.close()
        return

    if persistence.backend == "postgres":
        if (
            AsyncPostgresSaver is None or AsyncConnectionPool is None
        ):  # pragma: no cover
            msg = (
                "Postgres backend requires psycopg_pool and langgraph postgres extras."
            )
            raise RuntimeError(msg)

        dsn = persistence.postgres_dsn
        if dsn is None:  # pragma: no cover - defensive, validated earlier
            msg = "Postgres backend requires ORCHEO_POSTGRES_DSN to be set."
            raise RuntimeError(msg)

        pool = AsyncConnectionPool(dsn)
        try:
            async with pool.connection() as conn:  # type: ignore[assignment]
                yield AsyncPostgresSaver(cast(Any, conn))
        finally:
            await pool.close()
        return

    msg = "Unsupported checkpoint backend configured."
    raise ValueError(msg)
