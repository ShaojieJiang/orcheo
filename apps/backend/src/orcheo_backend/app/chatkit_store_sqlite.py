"""SQLite-backed store for ChatKit conversations."""

from __future__ import annotations
import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
import aiosqlite
from chatkit.store import NotFoundError, Store
from chatkit.types import Attachment, Page, ThreadItem, ThreadMetadata
from pydantic import TypeAdapter


if TYPE_CHECKING:  # pragma: no cover - typing only
    from orcheo_backend.app.chatkit_service import ChatKitRequestContext
else:  # pragma: no cover - fallback for runtime typing
    ChatKitRequestContext = dict[str, Any]


_THREAD_ADAPTER: TypeAdapter[ThreadMetadata] = TypeAdapter(ThreadMetadata)
_ITEM_ADAPTER: TypeAdapter[ThreadItem] = TypeAdapter(ThreadItem)
_ATTACHMENT_ADAPTER: TypeAdapter[Attachment] = TypeAdapter(Attachment)


logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


class SqliteChatKitStore(Store[ChatKitRequestContext]):
    """Persist ChatKit threads, items, and attachments in SQLite."""

    def __init__(self, database_path: str | Path) -> None:
        """Initialise the store backed by ``database_path``."""
        self._database_path = Path(database_path).expanduser()
        self._lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def load_thread(
        self, thread_id: str, context: ChatKitRequestContext
    ) -> ThreadMetadata:
        """Return metadata for the stored thread."""
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
        return self._row_to_thread(row)

    async def save_thread(
        self, thread: ThreadMetadata, context: ChatKitRequestContext
    ) -> None:
        """Persist thread metadata and merge workflow references."""
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                status_payload = (
                    thread.status.model_dump(mode="json")
                    if hasattr(thread.status, "model_dump")
                    else thread.status
                )
                metadata_payload = self._merge_metadata_from_context(
                    thread,
                    context,
                )
                workflow_id = metadata_payload.get("workflow_id")
                updated_at = _now()
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
                        _json_dumps(status_payload),
                        _json_dumps(metadata_payload),
                        _to_iso(thread.created_at),
                        _to_iso(updated_at),
                    ),
                )
                await conn.commit()

    @staticmethod
    def _merge_metadata_from_context(
        thread: ThreadMetadata,
        context: ChatKitRequestContext | None,
    ) -> dict[str, Any]:
        existing = dict(thread.metadata or {})
        if not context:
            return existing

        request = context.get("chatkit_request")
        metadata = getattr(request, "metadata", None)
        if isinstance(metadata, dict) and metadata:
            merged = {**existing, **metadata}
            thread.metadata = merged
            return merged

        thread.metadata = existing
        return existing

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
        threads = [self._row_to_thread(row) for row in sliced]
        next_after = threads[-1].id if has_more and threads else None
        return Page(data=threads, has_more=has_more, after=next_after)

    async def delete_thread(
        self, thread_id: str, context: ChatKitRequestContext
    ) -> None:
        """Remove a thread and cascade associated records."""
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                await conn.execute(
                    "DELETE FROM chat_threads WHERE id = ?",
                    (thread_id,),
                )
                await conn.commit()

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: ChatKitRequestContext,
    ) -> Page[ThreadItem]:
        """Return paginated items stored for ``thread_id``."""
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
        items = [self._row_to_item(row) for row in sliced]
        next_after = items[-1].id if has_more and items else None
        return Page(data=items, has_more=has_more, after=next_after)

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: ChatKitRequestContext
    ) -> None:
        """Append ``item`` to the persisted thread history."""
        await self._ensure_initialized()
        if item.thread_id != thread_id:
            raise ValueError("Thread item does not belong to the provided thread")
        async with self._lock:
            async with self._connection() as conn:
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
                        _json_dumps(_ITEM_ADAPTER.dump_python(item, mode="json")),
                        _to_iso(item.created_at),
                    ),
                )
                await self._touch_thread(conn, thread_id)
                await conn.commit()

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: ChatKitRequestContext
    ) -> None:
        """Insert or update a thread item."""
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                cursor = await conn.execute(
                    "SELECT ordinal FROM chat_messages WHERE id = ?",
                    (item.id,),
                )
                row = await cursor.fetchone()
                payload = _json_dumps(_ITEM_ADAPTER.dump_python(item, mode="json"))
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
                            _to_iso(item.created_at),
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
                            _to_iso(item.created_at),
                            item.id,
                        ),
                    )
                await self._touch_thread(conn, thread_id)
                await conn.commit()

    async def load_item(
        self, thread_id: str, item_id: str, context: ChatKitRequestContext
    ) -> ThreadItem:
        """Return an individual thread item."""
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
        return self._row_to_item(row)

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: ChatKitRequestContext
    ) -> None:
        """Remove an item from the persisted history."""
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                await conn.execute(
                    "DELETE FROM chat_messages WHERE id = ? AND thread_id = ?",
                    (item_id, thread_id),
                )
                await self._touch_thread(conn, thread_id)
                await conn.commit()

    async def save_attachment(
        self, attachment: Attachment, context: ChatKitRequestContext
    ) -> None:
        """Persist metadata for an attachment."""
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                thread_id = self._infer_thread_id(context)
                await conn.execute(
                    """
                    INSERT INTO chat_attachments (
                        id,
                        thread_id,
                        attachment_type,
                        name,
                        mime_type,
                        details_json,
                        storage_path,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        thread_id = excluded.thread_id,
                        attachment_type = excluded.attachment_type,
                        name = excluded.name,
                        mime_type = excluded.mime_type,
                        details_json = excluded.details_json,
                        storage_path = excluded.storage_path,
                        created_at = excluded.created_at
                    """,
                    (
                        attachment.id,
                        thread_id,
                        getattr(attachment, "type", None),
                        attachment.name,
                        attachment.mime_type,
                        _json_dumps(
                            _ATTACHMENT_ADAPTER.dump_python(attachment, mode="json")
                        ),
                        None,
                        _to_iso(_now()),
                    ),
                )
                await conn.commit()

    async def load_attachment(
        self, attachment_id: str, context: ChatKitRequestContext
    ) -> Attachment:
        """Return stored metadata for ``attachment_id``."""
        await self._ensure_initialized()
        async with self._connection() as conn:
            cursor = await conn.execute(
                """
                SELECT details_json FROM chat_attachments WHERE id = ?
                """,
                (attachment_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            raise NotFoundError(f"Attachment {attachment_id} not found")
        return _ATTACHMENT_ADAPTER.validate_python(json.loads(row["details_json"]))

    async def delete_attachment(
        self, attachment_id: str, context: ChatKitRequestContext
    ) -> None:
        """Remove attachment metadata."""
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                await conn.execute(
                    "DELETE FROM chat_attachments WHERE id = ?",
                    (attachment_id,),
                )
                await conn.commit()

    async def prune_threads_older_than(self, cutoff: datetime) -> int:
        """Delete threads and attachments not updated since ``cutoff``."""
        await self._ensure_initialized()
        cutoff_iso = _to_iso(cutoff)
        async with self._lock:
            async with self._connection() as conn:
                cursor = await conn.execute(
                    "SELECT id FROM chat_threads WHERE updated_at < ?",
                    (cutoff_iso,),
                )
                rows = await cursor.fetchall()
                thread_ids = [row["id"] for row in rows]

                if not thread_ids:
                    return 0

                attachment_paths: list[str] = []
                for thread_id in thread_ids:
                    cursor = await conn.execute(
                        """
                        SELECT storage_path
                          FROM chat_attachments
                         WHERE thread_id = ? AND storage_path IS NOT NULL
                        """,
                        (thread_id,),
                    )
                    attachment_paths.extend(
                        row["storage_path"]
                        for row in await cursor.fetchall()
                        if row["storage_path"]
                    )

                for thread_id in thread_ids:
                    await conn.execute(
                        "DELETE FROM chat_attachments WHERE thread_id = ?",
                        (thread_id,),
                    )
                    await conn.execute(
                        "DELETE FROM chat_threads WHERE id = ?",
                        (thread_id,),
                    )

                await conn.commit()

        for path_str in attachment_paths:
            try:
                Path(path_str).unlink(missing_ok=True)
            except Exception:  # pragma: no cover - best effort cleanup
                logger.warning(
                    "Failed to delete ChatKit attachment file",
                    extra={"storage_path": path_str},
                    exc_info=True,
                )

        return len(thread_ids)

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
                await self._run_migrations(conn)
                await conn.executescript(
                    """
                    PRAGMA journal_mode = WAL;
                    CREATE TABLE IF NOT EXISTS chat_threads (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        workflow_id TEXT,
                        status_json TEXT NOT NULL,
                        metadata_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id TEXT PRIMARY KEY,
                        thread_id TEXT NOT NULL,
                        ordinal INTEGER NOT NULL,
                        item_type TEXT,
                        item_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(thread_id) REFERENCES chat_threads(id)
                            ON DELETE CASCADE
                    );
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_thread
                        ON chat_messages(thread_id, ordinal);
                    CREATE TABLE IF NOT EXISTS chat_attachments (
                        id TEXT PRIMARY KEY,
                        thread_id TEXT,
                        attachment_type TEXT NOT NULL,
                        name TEXT NOT NULL,
                        mime_type TEXT NOT NULL,
                        details_json TEXT NOT NULL,
                        storage_path TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(thread_id) REFERENCES chat_threads(id)
                            ON DELETE SET NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_chat_attachments_thread
                        ON chat_attachments(thread_id);
                    """
                )
                await conn.commit()
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
            (_to_iso(_now()), thread_id),
        )

    @staticmethod
    def _row_to_thread(row: aiosqlite.Row) -> ThreadMetadata:
        data = {
            "id": row["id"],
            "title": row["title"],
            "created_at": datetime.fromisoformat(row["created_at"]),
            "status": json.loads(row["status_json"]),
            "metadata": json.loads(row["metadata_json"]),
        }
        return _THREAD_ADAPTER.validate_python(data)

    @staticmethod
    def _row_to_item(row: aiosqlite.Row) -> ThreadItem:
        payload = json.loads(row["item_json"])
        payload.setdefault("id", row["id"])
        payload.setdefault("thread_id", row["thread_id"])
        payload.setdefault("created_at", row["created_at"])
        if isinstance(payload.get("created_at"), str):
            payload["created_at"] = datetime.fromisoformat(payload["created_at"])
        return _ITEM_ADAPTER.validate_python(payload)

    @staticmethod
    def _infer_thread_id(context: ChatKitRequestContext) -> str | None:
        request = context.get("chatkit_request") if context else None
        params = getattr(request, "params", None)
        candidate = getattr(params, "thread_id", None)
        if candidate:
            return str(candidate)
        return None

    async def _run_migrations(self, conn: aiosqlite.Connection) -> None:
        await self._migrate_chat_messages_thread_id(conn)

    async def _migrate_chat_messages_thread_id(
        self, conn: aiosqlite.Connection
    ) -> None:
        cursor = await conn.execute(
            """
            SELECT name
              FROM sqlite_master
             WHERE type = 'table' AND name = 'chat_messages'
            """
        )
        table = await cursor.fetchone()
        if table is None:
            return

        cursor = await conn.execute("PRAGMA table_info(chat_messages)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "thread_id" in columns:
            return

        logger.info("Migrating chat_messages table to add thread_id column")
        cursor = await conn.execute(
            """
            SELECT id, ordinal, item_type, item_json, created_at
              FROM chat_messages
             ORDER BY ordinal
            """
        )
        rows = await cursor.fetchall()

        await conn.execute("PRAGMA foreign_keys = OFF;")
        await conn.execute("DROP TABLE IF EXISTS chat_messages__new;")
        await conn.execute("BEGIN;")
        try:
            await conn.execute(
                """
                CREATE TABLE chat_messages__new (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    item_type TEXT,
                    item_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(thread_id) REFERENCES chat_threads(id)
                        ON DELETE CASCADE
                )
                """
            )

            for row in rows:
                payload = json.loads(row["item_json"])
                thread_id = (
                    payload.get("thread_id")
                    or payload.get("threadId")
                    or payload.get("metadata", {}).get("thread_id")
                )
                if thread_id is None:
                    logger.warning(
                        (
                            "Dropping message %s while migrating chat_messages; "
                            "missing thread_id"
                        ),
                        row["id"],
                    )
                    continue

                await conn.execute(
                    """
                    INSERT INTO chat_messages__new (
                        id,
                        thread_id,
                        ordinal,
                        item_type,
                        item_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"],
                        str(thread_id),
                        row["ordinal"],
                        row["item_type"],
                        row["item_json"],
                        row["created_at"],
                    ),
                )

            await conn.execute("DROP TABLE chat_messages;")
            await conn.execute(
                "ALTER TABLE chat_messages__new RENAME TO chat_messages;"
            )
            await conn.commit()
            logger.info("chat_messages migration completed successfully")
        except Exception:
            await conn.rollback()
            logger.exception(
                "Failed to migrate chat_messages table to include thread_id column"
            )
            raise
        finally:
            await conn.execute("PRAGMA foreign_keys = ON;")


__all__ = ["SqliteChatKitStore"]
