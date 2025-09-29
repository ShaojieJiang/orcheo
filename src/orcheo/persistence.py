"""Persistence helpers that create LangGraph checkpoint savers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import aiosqlite

from orcheo.config import Settings

try:  # pragma: no cover - import guarded for optional dependency
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg_pool import AsyncConnectionPool
except Exception:  # pragma: no cover - fallback when dependency missing
    AsyncPostgresSaver = None  # type: ignore[assignment]
    AsyncConnectionPool = None  # type: ignore[assignment]

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


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
        if AsyncPostgresSaver is None or AsyncConnectionPool is None:  # pragma: no cover
            msg = "Postgres backend requires psycopg_pool and langgraph postgres extras."
            raise RuntimeError(msg)

        pool = AsyncConnectionPool(persistence.postgres_dsn)
        try:
            async with pool.connection() as conn:  # type: ignore[assignment]
                yield AsyncPostgresSaver(conn)
        finally:
            await pool.close()
        return

    msg = "Unsupported checkpoint backend configured."
    raise ValueError(msg)

