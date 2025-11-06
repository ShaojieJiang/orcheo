"""Pruning behavior tests for the SQLite-backed ChatKit store."""

from __future__ import annotations
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
import pytest
from chatkit.store import NotFoundError
from chatkit.types import ThreadMetadata
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore


def _timestamp() -> datetime:
    return datetime.now(tz=UTC)


@pytest.mark.asyncio
async def test_prune_threads_older_than(tmp_path: Path) -> None:
    """Stale threads and attachments should be removed when pruned."""

    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    recent_thread = ThreadMetadata(
        id="thr_recent",
        created_at=_timestamp(),
        metadata={"workflow_id": "recent"},
    )
    stale_thread = ThreadMetadata(
        id="thr_stale",
        created_at=_timestamp(),
        metadata={"workflow_id": "stale"},
    )

    await store.save_thread(recent_thread, context)
    await store.save_thread(stale_thread, context)

    cutoff = datetime.now(tz=UTC) - timedelta(days=30)
    stale_timestamp = (cutoff - timedelta(days=1)).isoformat()
    attachment_path = tmp_path / "stale.txt"
    attachment_path.write_text("unused", encoding="utf-8")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
            (stale_timestamp, stale_thread.id),
        )
        conn.execute(
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
            """,
            (
                "atc_stale",
                stale_thread.id,
                "file",
                "stale.txt",
                "text/plain",
                json.dumps(
                    {
                        "id": "atc_stale",
                        "type": "file",
                        "name": "stale.txt",
                        "mime_type": "text/plain",
                    },
                    separators=(",", ":"),
                    ensure_ascii=False,
                ),
                str(attachment_path),
                _timestamp().isoformat(),
            ),
        )
        conn.commit()

    removed = await store.prune_threads_older_than(cutoff)

    assert removed == 1
    with pytest.raises(NotFoundError):
        await store.load_thread(stale_thread.id, context)
    loaded_recent = await store.load_thread(recent_thread.id, context)
    assert loaded_recent.id == recent_thread.id
    assert not attachment_path.exists()


@pytest.mark.asyncio
async def test_sqlite_store_prune_threads_no_old_threads(tmp_path: Path) -> None:
    """Prune should return 0 when no threads are old enough."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    thread = ThreadMetadata(id="thr_new", created_at=_timestamp())
    await store.save_thread(thread, context)

    cutoff = datetime.now(tz=UTC) - timedelta(days=30)
    removed = await store.prune_threads_older_than(cutoff)

    assert removed == 0
