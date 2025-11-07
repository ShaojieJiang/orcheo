"""Base class that manages the SQLite connection and schema."""

from __future__ import annotations
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
import aiosqlite
from chatkit.store import Store
from orcheo_backend.app.chatkit_store_sqlite.schema import ensure_schema
from orcheo_backend.app.chatkit_store_sqlite.types import ChatKitRequestContext
from orcheo_backend.app.chatkit_store_sqlite.utils import now_utc, to_isoformat


class BaseSqliteStore(Store[ChatKitRequestContext]):
    """Manage the SQLite connection pool and lifecycle."""

    def __init__(self, database_path: str | Path) -> None:
        """Initialise the store with the provided database path."""
        self._database_path = Path(database_path).expanduser()
        self._lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()
        self._initialized = False

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[aiosqlite.Connection]:
        conn = await aiosqlite.connect(self._database_path)
        try:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON;")
            yield conn
        finally:
            await conn.close()

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            self._database_path.parent.mkdir(parents=True, exist_ok=True)
            async with self._connection() as conn:
                await ensure_schema(conn)
            self._initialized = True

    async def _next_item_ordinal(
        self, conn: aiosqlite.Connection, thread_id: str
    ) -> int:
        cursor = await conn.execute(
            (
                "SELECT COALESCE(MAX(ordinal), -1) AS current "
                "FROM chat_messages WHERE thread_id = ?"
            ),
            (thread_id,),
        )
        row = await cursor.fetchone()
        current = row["current"] if row is not None else -1
        return int(current) + 1

    async def _touch_thread(self, conn: aiosqlite.Connection, thread_id: str) -> None:
        await conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
            (to_isoformat(now_utc()), thread_id),
        )


__all__ = ["BaseSqliteStore"]
