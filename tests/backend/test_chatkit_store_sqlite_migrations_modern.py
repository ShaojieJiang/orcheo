"""Modern migration tests for the SQLite ChatKit store."""

from __future__ import annotations
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
import pytest
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore


def _timestamp() -> datetime:
    return datetime.now(tz=UTC)


@pytest.mark.asyncio
async def test_sqlite_store_no_migration_when_thread_id_exists(tmp_path: Path) -> None:
    """Migration should skip when thread_id column already exists."""
    db_path = tmp_path / "modern.sqlite"
    thread_id = "thr_modern"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE chat_threads (
                id TEXT PRIMARY KEY,
                title TEXT,
                workflow_id TEXT,
                status_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        now_iso = _timestamp().isoformat()
        conn.execute(
            """
            INSERT INTO chat_threads VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                thread_id,
                None,
                "wf_test",
                json.dumps({"type": "active"}),
                json.dumps({}),
                now_iso,
                now_iso,
            ),
        )

        conn.execute(
            """
            CREATE TABLE chat_messages (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                item_type TEXT,
                item_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO chat_messages VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "msg_modern",
                thread_id,
                0,
                "user_message",
                json.dumps(
                    {
                        "type": "user_message",
                        "id": "msg_modern",
                        "thread_id": thread_id,
                        "content": [{"type": "input_text", "text": "Test"}],
                        "attachments": [],
                        "quoted_text": None,
                        "inference_options": {},
                    }
                ),
                now_iso,
            ),
        )
        conn.commit()

    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    items = await store.load_thread_items(
        thread_id, after=None, limit=10, order="asc", context=context
    )
    assert len(items.data) == 1
    assert items.data[0].id == "msg_modern"


@pytest.mark.asyncio
async def test_migrate_chat_messages_migration_failure(tmp_path: Path) -> None:
    """Migration should handle failures gracefully."""
    db_path = tmp_path / "migration_fail.sqlite"
    thread_id = "thr_fail"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE chat_threads (
                id TEXT PRIMARY KEY,
                title TEXT,
                workflow_id TEXT,
                status_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        now_iso = _timestamp().isoformat()
        conn.execute(
            """
            INSERT INTO chat_threads VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                thread_id,
                None,
                "wf_test",
                json.dumps({"type": "active"}),
                json.dumps({}),
                now_iso,
                now_iso,
            ),
        )

        conn.execute(
            """
            CREATE TABLE chat_messages (
                id TEXT PRIMARY KEY,
                ordinal INTEGER NOT NULL,
                item_type TEXT,
                item_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO chat_messages VALUES (?, ?, ?, ?, ?)
            """,
            (
                "msg_corrupt",
                0,
                "user_message",
                "THIS IS NOT VALID JSON",
                now_iso,
            ),
        )
        conn.commit()

    with pytest.raises(json.JSONDecodeError):
        store = SqliteChatKitStore(db_path)
        context: dict[str, object] = {}
        await store.load_thread_items(
            thread_id, after=None, limit=10, order="asc", context=context
        )
