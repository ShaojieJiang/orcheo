"""Thread-level operations for the SQLite ChatKit store."""

from __future__ import annotations
from typing import Any
from chatkit.store import NotFoundError
from chatkit.types import Page, ThreadMetadata
from orcheo_backend.app.chatkit_store_sqlite.base import BaseSqliteStore
from orcheo_backend.app.chatkit_store_sqlite.serialization import (
    serialize_thread_status,
    thread_from_row,
)
from orcheo_backend.app.chatkit_store_sqlite.types import ChatKitRequestContext
from orcheo_backend.app.chatkit_store_sqlite.utils import (
    compact_json,
    now_utc,
    to_isoformat,
)


class ThreadStoreMixin(BaseSqliteStore):
    """CRUD helpers for thread metadata."""

    async def load_thread(
        self, thread_id: str, context: ChatKitRequestContext
    ) -> ThreadMetadata:
        """Return metadata for ``thread_id``."""
        await self._ensure_initialized()
        async with self._connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, title, status_json, metadata_json, created_at
                  FROM chat_threads
                 WHERE id = ?
                """,
                (thread_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            raise NotFoundError(f"Thread {thread_id} not found")
        return thread_from_row(row)

    async def save_thread(
        self, thread: ThreadMetadata, context: ChatKitRequestContext
    ) -> None:
        """Insert or update metadata for ``thread``."""
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                metadata_payload = self._merge_metadata_from_context(thread, context)
                workflow_id = metadata_payload.get("workflow_id")
                updated_at = to_isoformat(now_utc())
                await conn.execute(
                    """
                    INSERT INTO chat_threads (
                        id,
                        title,
                        workflow_id,
                        status_json,
                        metadata_json,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title = excluded.title,
                        workflow_id = excluded.workflow_id,
                        status_json = excluded.status_json,
                        metadata_json = excluded.metadata_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        thread.id,
                        thread.title,
                        str(workflow_id) if workflow_id else None,
                        serialize_thread_status(thread),
                        compact_json(metadata_payload),
                        to_isoformat(thread.created_at),
                        updated_at,
                    ),
                )
                await conn.commit()

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: ChatKitRequestContext,
    ) -> Page[ThreadMetadata]:
        """Return a paginated collection of threads."""
        await self._ensure_initialized()
        limit = max(limit, 1)
        ordering = "asc" if order.lower() == "asc" else "desc"
        comparator = ">" if ordering == "asc" else "<"
        async with self._connection() as conn:
            params: list[Any] = []
            where_clause = ""
            if after:
                cursor = await conn.execute(
                    "SELECT created_at, id FROM chat_threads WHERE id = ?",
                    (after,),
                )
                marker = await cursor.fetchone()
                if marker is not None:
                    created_at = marker["created_at"]
                    where_clause = (
                        f" WHERE (created_at {comparator} ?)"
                        f" OR (created_at = ? AND id {comparator} ?)"
                    )
                    params.extend([created_at, created_at, marker["id"]])

            query = (
                "SELECT id, title, status_json, metadata_json, created_at "
                "FROM chat_threads"
            )
            if where_clause:
                query += where_clause
            query += f" ORDER BY created_at {ordering.upper()}, id {ordering.upper()}"
            query += " LIMIT ?"
            params.append(limit + 1)

            cursor = await conn.execute(query, tuple(params))
            rows = list(await cursor.fetchall())

        has_more = len(rows) > limit
        sliced = rows[:limit]
        threads = [thread_from_row(row) for row in sliced]
        next_after = threads[-1].id if has_more and threads else None
        return Page(data=threads, has_more=has_more, after=next_after)

    async def delete_thread(
        self, thread_id: str, context: ChatKitRequestContext
    ) -> None:
        """Remove ``thread_id`` and cascade associated entities."""
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                await conn.execute(
                    "DELETE FROM chat_threads WHERE id = ?",
                    (thread_id,),
                )
                await conn.commit()

    @staticmethod
    def _merge_metadata_from_context(
        thread: ThreadMetadata, context: ChatKitRequestContext | None
    ) -> dict[str, Any]:
        existing = dict(thread.metadata or {})
        if not context:
            thread.metadata = existing
            return existing

        request = context.get("chatkit_request")
        metadata = getattr(request, "metadata", None)
        if isinstance(metadata, dict) and metadata:
            merged = {**existing, **metadata}
            thread.metadata = merged
            return merged

        thread.metadata = existing
        return existing


__all__ = ["ThreadStoreMixin"]
