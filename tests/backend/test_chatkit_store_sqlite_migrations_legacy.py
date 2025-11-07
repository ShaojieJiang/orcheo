"""Legacy migration tests for the SQLite ChatKit store."""

from __future__ import annotations
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
import pytest
from chatkit.types import (
    InferenceOptions,
    ThreadItem,
    UserMessageItem,
    UserMessageTextContent,
)
from pydantic import TypeAdapter
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore


def _timestamp() -> datetime:
    return datetime.now(tz=UTC)


@pytest.mark.asyncio
async def test_migrates_chat_messages_thread_id_column(tmp_path: Path) -> None:
    """Legacy databases without the thread_id column should be upgraded."""

    db_path = tmp_path / "legacy.sqlite"
    thread_id = "thr_legacy"
    message_created_at = _timestamp()

    user_item = UserMessageItem(
        id="msg_legacy",
        thread_id=thread_id,
        created_at=message_created_at,
        content=[UserMessageTextContent(type="input_text", text="Hello")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    item_payload = TypeAdapter(ThreadItem).dump_python(user_item, mode="json")

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
            INSERT INTO chat_threads (
                id,
                title,
                workflow_id,
                status_json,
                metadata_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                thread_id,
                None,
                "wf_legacy",
                json.dumps({"type": "active"}),
                json.dumps({"workflow_id": "wf_legacy"}),
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
            INSERT INTO chat_messages (
                id,
                ordinal,
                item_type,
                item_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_item.id,
                0,
                user_item.type,
                json.dumps(item_payload, separators=(",", ":"), ensure_ascii=False),
                message_created_at.isoformat(),
            ),
        )

    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    items_page = await store.load_thread_items(
        thread_id,
        after=None,
        limit=10,
        order="asc",
        context=context,
    )
    assert len(items_page.data) == 1
    assert items_page.data[0].thread_id == thread_id
    assert items_page.data[0].id == user_item.id

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(chat_messages)")}
        assert "thread_id" in columns


@pytest.mark.asyncio
async def test_migrate_chat_messages_drop_message_without_thread_id(
    tmp_path: Path,
) -> None:
    """Migration should drop messages without thread_id in payload."""
    db_path = tmp_path / "legacy_no_tid.sqlite"
    thread_id = "thr_for_migration"

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
                "msg_no_tid",
                0,
                "user_message",
                json.dumps({"type": "user_message", "id": "msg_no_tid"}),
                now_iso,
            ),
        )
        conn.commit()

    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    items = await store.load_thread_items(
        thread_id, after=None, limit=10, order="asc", context=context
    )
    assert len(items.data) == 0
