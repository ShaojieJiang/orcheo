"""Thread item operations for the SQLite ChatKit store."""

from __future__ import annotations
from typing import Any
from chatkit.store import NotFoundError
from chatkit.types import Page, ThreadItem
from orcheo_backend.app.chatkit_store_sqlite.base import BaseSqliteStore
from orcheo_backend.app.chatkit_store_sqlite.serialization import (
    item_from_row,
    serialize_item,
)
from orcheo_backend.app.chatkit_store_sqlite.types import ChatKitRequestContext
from orcheo_backend.app.chatkit_store_sqlite.utils import to_isoformat


class ThreadItemStoreMixin(BaseSqliteStore):
    """CRUD helpers for thread items."""

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: ChatKitRequestContext,
    ) -> Page[ThreadItem]:
        """Return paginated items for ``thread_id``."""
        await self._ensure_initialized()
        limit = max(limit, 1)
        ordering = "asc" if order.lower() == "asc" else "desc"
        comparator = ">" if ordering == "asc" else "<"
        async with self._connection() as conn:
            params: list[Any] = [thread_id]
            where_clause = ""
            if after:
                cursor = await conn.execute(
                    """
                    SELECT ordinal FROM chat_messages
                     WHERE id = ? AND thread_id = ?
                    """,
                    (after, thread_id),
                )
                marker = await cursor.fetchone()
                if marker is not None:
                    ordinal = marker["ordinal"]
                    where_clause = f" AND ordinal {comparator} ?"
                    params.append(ordinal)

            query = (
                "SELECT id, thread_id, ordinal, item_type, item_json, created_at "
                "FROM chat_messages WHERE thread_id = ?"
            )
            if where_clause:
                query += where_clause
            query += f" ORDER BY ordinal {ordering.upper()}, id {ordering.upper()}"
            query += " LIMIT ?"
            params.append(limit + 1)

            cursor = await conn.execute(query, tuple(params))
            rows = list(await cursor.fetchall())

        has_more = len(rows) > limit
        sliced = rows[:limit]
        items = [item_from_row(row) for row in sliced]
        next_after = items[-1].id if has_more and items else None
        return Page(data=items, has_more=has_more, after=next_after)

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: ChatKitRequestContext
    ) -> None:
        """Append ``item`` to the stored history for ``thread_id``."""
        await self._ensure_initialized()
        if item.thread_id != thread_id:
            raise ValueError("Thread item does not belong to the provided thread")
        async with self._lock:
            async with self._connection() as conn:
                ordinal = await self._next_item_ordinal(conn, thread_id)
                payload = serialize_item(item)
                await conn.execute(
                    """
                    INSERT INTO chat_messages (
                        id,
                        thread_id,
                        ordinal,
                        item_type,
                        item_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        thread_id = excluded.thread_id,
                        item_type = excluded.item_type,
                        item_json = excluded.item_json,
                        created_at = excluded.created_at
                    """,
                    (
                        item.id,
                        thread_id,
                        ordinal,
                        getattr(item, "type", None),
                        payload,
                        to_isoformat(item.created_at),
                    ),
                )
                await self._touch_thread(conn, thread_id)
                await conn.commit()

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: ChatKitRequestContext
    ) -> None:
        """Insert or update a single thread item."""
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                cursor = await conn.execute(
                    "SELECT ordinal FROM chat_messages WHERE id = ?",
                    (item.id,),
                )
                row = await cursor.fetchone()
                payload = serialize_item(item)
                if row is None:
                    ordinal = await self._next_item_ordinal(conn, thread_id)
                    await conn.execute(
                        """
                        INSERT INTO chat_messages (
                            id,
                            thread_id,
                            ordinal,
                            item_type,
                            item_json,
                            created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item.id,
                            thread_id,
                            ordinal,
                            getattr(item, "type", None),
                            payload,
                            to_isoformat(item.created_at),
                        ),
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE chat_messages
                           SET thread_id = ?,
                               item_type = ?,
                               item_json = ?,
                               created_at = ?
                         WHERE id = ?
                        """,
                        (
                            thread_id,
                            getattr(item, "type", None),
                            payload,
                            to_isoformat(item.created_at),
                            item.id,
                        ),
                    )
                await self._touch_thread(conn, thread_id)
                await conn.commit()

    async def load_item(
        self, thread_id: str, item_id: str, context: ChatKitRequestContext
    ) -> ThreadItem:
        """Return a persisted item for ``item_id``."""
        await self._ensure_initialized()
        async with self._connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, thread_id, ordinal, item_type, item_json, created_at
                  FROM chat_messages
                 WHERE id = ? AND thread_id = ?
                """,
                (item_id, thread_id),
            )
            row = await cursor.fetchone()
        if row is None:
            raise NotFoundError(f"Item {item_id} not found in thread {thread_id}")
        return item_from_row(row)

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: ChatKitRequestContext
    ) -> None:
        """Remove ``item_id`` from the history."""
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                await conn.execute(
                    "DELETE FROM chat_messages WHERE id = ? AND thread_id = ?",
                    (item_id, thread_id),
                )
                await self._touch_thread(conn, thread_id)
                await conn.commit()


__all__ = ["ThreadItemStoreMixin"]
