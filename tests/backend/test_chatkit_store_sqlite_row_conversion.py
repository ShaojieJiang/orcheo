"""Row conversion tests for the SQLite ChatKit store."""

from __future__ import annotations
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
import pytest
from chatkit.types import (
    ThreadMetadata,
)
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore


def _timestamp() -> datetime:
    return datetime.now(tz=UTC)


@pytest.mark.asyncio
async def test_sqlite_store_row_to_item_with_string_created_at(tmp_path: Path) -> None:
    """Row to item conversion should handle string created_at in payload."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}
    thread_id = "thr_string_date"

    thread = ThreadMetadata(id=thread_id, created_at=_timestamp())
    await store.save_thread(thread, context)

    created_time = datetime(2024, 1, 1, hour=12, tzinfo=UTC)
    item_payload = {
        "type": "user_message",
        "id": "msg_str_date",
        "thread_id": thread_id,
        "created_at": created_time.isoformat(),
        "content": [{"type": "input_text", "text": "Test"}],
        "attachments": [],
        "quoted_text": None,
        "inference_options": {},
    }

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (
                id, thread_id, ordinal, item_type, item_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "msg_str_date",
                thread_id,
                0,
                "user_message",
                json.dumps(item_payload),
                created_time.isoformat(),
            ),
        )
        conn.commit()

    loaded = await store.load_item(thread_id, "msg_str_date", context)
    assert loaded.id == "msg_str_date"
    assert isinstance(loaded.created_at, datetime)


@pytest.mark.asyncio
async def test_sqlite_store_row_to_item_missing_created_at_in_payload(
    tmp_path: Path,
) -> None:
    """Row to item should use row created_at when missing from payload."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}
    thread_id = "thr_no_created"

    thread = ThreadMetadata(id=thread_id, created_at=_timestamp())
    await store.save_thread(thread, context)

    created_time = datetime(2024, 1, 1, hour=12, tzinfo=UTC)
    item_payload = {
        "type": "user_message",
        "content": [{"type": "input_text", "text": "Test"}],
        "attachments": [],
        "quoted_text": None,
        "inference_options": {},
    }

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (
                id, thread_id, ordinal, item_type, item_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "msg_no_created",
                thread_id,
                0,
                "user_message",
                json.dumps(item_payload),
                created_time.isoformat(),
            ),
        )
        conn.commit()

    loaded = await store.load_item(thread_id, "msg_no_created", context)
    assert loaded.id == "msg_no_created"
    assert isinstance(loaded.created_at, datetime)
    assert loaded.created_at == created_time


@pytest.mark.asyncio
async def test_sqlite_store_row_to_item_with_datetime_created_at(
    tmp_path: Path,
) -> None:
    """Row to item conversion should handle datetime created_at in payload."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}
    thread_id = "thr_datetime"

    thread = ThreadMetadata(id=thread_id, created_at=_timestamp())
    await store.save_thread(thread, context)

    created_time = datetime(2024, 1, 1, hour=12, tzinfo=UTC)
    item_payload = {
        "type": "user_message",
        "id": "msg_datetime",
        "thread_id": thread_id,
        "created_at": created_time,
        "content": [{"type": "input_text", "text": "Test"}],
        "attachments": [],
        "quoted_text": None,
        "inference_options": {},
    }

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (
                id, thread_id, ordinal, item_type, item_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "msg_datetime",
                thread_id,
                0,
                "user_message",
                json.dumps(item_payload, default=str),
                created_time.isoformat(),
            ),
        )
        conn.commit()

    loaded = await store.load_item(thread_id, "msg_datetime", context)
    assert loaded.id == "msg_datetime"
    assert isinstance(loaded.created_at, datetime)


@pytest.mark.asyncio
async def test_sqlite_store_row_to_item_with_non_string_created_at(
    tmp_path: Path,
) -> None:
    """Row to item should handle non-string created_at in payload."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}
    thread_id = "thr_non_str_date"

    thread = ThreadMetadata(id=thread_id, created_at=_timestamp())
    await store.save_thread(thread, context)

    created_time = datetime(2024, 6, 15, hour=10, tzinfo=UTC)
    item_payload = {
        "type": "user_message",
        "id": "msg_non_str",
        "thread_id": thread_id,
        "created_at": 1234567890,
        "content": [{"type": "input_text", "text": "Test"}],
        "attachments": [],
        "quoted_text": None,
        "inference_options": {},
    }

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (
                id, thread_id, ordinal, item_type, item_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "msg_non_str",
                thread_id,
                0,
                "user_message",
                json.dumps(item_payload),
                created_time.isoformat(),
            ),
        )
        conn.commit()

    loaded = await store.load_item(thread_id, "msg_non_str", context)
    assert loaded.id == "msg_non_str"
    assert isinstance(loaded.created_at, datetime)
