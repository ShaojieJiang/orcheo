"""Attachment handling and pruning logic for the PostgreSQL ChatKit store."""

from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path
from chatkit.store import NotFoundError
from chatkit.types import Attachment
from orcheo_backend.app.chatkit_store_postgres.base import BasePostgresStore
from orcheo_backend.app.chatkit_store_postgres.serialization import (
    attachment_from_details,
    serialize_attachment,
)
from orcheo_backend.app.chatkit_store_postgres.types import ChatKitRequestContext
from orcheo_backend.app.chatkit_store_postgres.utils import now_utc


logger = logging.getLogger(__name__)


class AttachmentStoreMixin(BasePostgresStore):
    """Manage attachments and pruning tasks."""

    async def save_attachment(
        self,
        attachment: Attachment,
        context: ChatKitRequestContext,
        *,
        storage_path: str | None = None,
    ) -> None:
        """Persist metadata for ``attachment``."""
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
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
                        serialize_attachment(attachment),
                        storage_path,
                        now_utc(),
                    ),
                )

    async def load_attachment(
        self, attachment_id: str, context: ChatKitRequestContext
    ) -> Attachment:
        """Return stored metadata for ``attachment_id``."""
        await self._ensure_initialized()
        async with self._connection() as conn:
            cursor = await conn.execute(
                "SELECT details_json FROM chat_attachments WHERE id = %s",
                (attachment_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            raise NotFoundError(f"Attachment {attachment_id} not found")
        return attachment_from_details(row["details_json"])

    async def delete_attachment(
        self, attachment_id: str, context: ChatKitRequestContext
    ) -> None:
        """Remove attachment metadata and any persisted file reference."""
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                await conn.execute(
                    "DELETE FROM chat_attachments WHERE id = %s",
                    (attachment_id,),
                )

    async def prune_threads_older_than(self, cutoff: datetime) -> int:
        """Delete threads (and attachments) that have not been updated recently."""
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                cursor = await conn.execute(
                    "SELECT id FROM chat_threads WHERE updated_at < %s",
                    (cutoff,),
                )
                rows = await cursor.fetchall()
                thread_ids = [row["id"] for row in rows]

                if not thread_ids:
                    return 0

                cursor = await conn.execute(
                    """
                    SELECT storage_path
                      FROM chat_attachments
                     WHERE thread_id = ANY(%s) AND storage_path IS NOT NULL
                    """,
                    (thread_ids,),
                )
                attachment_paths = [
                    row["storage_path"]
                    for row in await cursor.fetchall()
                    if row.get("storage_path")
                ]

                await conn.execute(
                    "DELETE FROM chat_attachments WHERE thread_id = ANY(%s)",
                    (thread_ids,),
                )
                await conn.execute(
                    "DELETE FROM chat_threads WHERE id = ANY(%s)",
                    (thread_ids,),
                )

        for path_str in attachment_paths:
            try:
                Path(path_str).unlink(missing_ok=True)
            except Exception:  # pragma: no cover - best-effort cleanup
                logger.warning(
                    "Failed to delete ChatKit attachment file",
                    extra={"storage_path": path_str},
                    exc_info=True,
                )

        return len(thread_ids)

    @staticmethod
    def _infer_thread_id(context: ChatKitRequestContext) -> str | None:
        request = context.get("chatkit_request") if context else None
        params = getattr(request, "params", None)
        candidate = getattr(params, "thread_id", None)
        if candidate:
            return str(candidate)
        return None


__all__ = ["AttachmentStoreMixin"]
