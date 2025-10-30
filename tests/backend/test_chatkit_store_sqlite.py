"""Tests for the SQLite-backed ChatKit store."""

from __future__ import annotations
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import pytest
from chatkit.store import NotFoundError
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    FileAttachment,
    InferenceOptions,
    ThreadItem,
    ThreadMetadata,
    UserMessageItem,
    UserMessageTextContent,
)
from pydantic import TypeAdapter
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore


def _timestamp() -> datetime:
    return datetime.now(tz=UTC)


@pytest.mark.asyncio
async def test_sqlite_store_persists_conversation(tmp_path: Path) -> None:
    """Threads, items, and attachments should round-trip through SQLite."""

    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    thread = ThreadMetadata(
        id="thr_sqlite",
        created_at=_timestamp(),
        metadata={"workflow_id": "abcd"},
    )
    await store.save_thread(thread, context)

    loaded_thread = await store.load_thread(thread.id, context)
    assert loaded_thread.metadata["workflow_id"] == "abcd"

    user_item = UserMessageItem(
        id="msg_user",
        thread_id=thread.id,
        created_at=_timestamp(),
        content=[UserMessageTextContent(type="input_text", text="Ping")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await store.add_thread_item(thread.id, user_item, context)

    items_page = await store.load_thread_items(
        thread.id,
        after=None,
        limit=10,
        order="asc",
        context=context,
    )
    assert len(items_page.data) == 1
    assert isinstance(items_page.data[0], UserMessageItem)

    assistant_item = AssistantMessageItem(
        id="msg_assistant",
        thread_id=thread.id,
        created_at=_timestamp(),
        content=[AssistantMessageContent(text="Pong")],
    )
    await store.save_item(thread.id, assistant_item, context)

    loaded_item = await store.load_item(thread.id, assistant_item.id, context)
    assert isinstance(loaded_item, AssistantMessageItem)
    assert loaded_item.content[0].text == "Pong"

    await store.delete_thread_item(thread.id, user_item.id, context)
    items_after_delete = await store.load_thread_items(
        thread.id,
        after=None,
        limit=10,
        order="asc",
        context=context,
    )
    assert len(items_after_delete.data) == 1
    assert items_after_delete.data[0].id == assistant_item.id

    attachment = FileAttachment(
        id="atc_file",
        name="demo.txt",
        mime_type="text/plain",
    )
    await store.save_attachment(attachment, context)

    loaded_attachment = await store.load_attachment(attachment.id, context)
    assert loaded_attachment.name == attachment.name

    await store.delete_attachment(attachment.id, context)
    with pytest.raises(NotFoundError):
        await store.load_attachment(attachment.id, context)

    await store.delete_thread(thread.id, context)
    with pytest.raises(NotFoundError):
        await store.load_thread(thread.id, context)


@pytest.mark.asyncio
async def test_sqlite_store_merges_metadata_from_context(tmp_path: Path) -> None:
    """Incoming ChatKit metadata should populate the stored thread."""

    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)

    request = SimpleNamespace(
        metadata={"workflow_id": "wf_ctx", "workflow_name": "Ctx"}
    )
    context: dict[str, object] = {"chatkit_request": request}

    thread = ThreadMetadata(
        id="thr_ctx",
        created_at=_timestamp(),
    )

    await store.save_thread(thread, context)

    assert thread.metadata["workflow_id"] == "wf_ctx"

    loaded_thread = await store.load_thread(thread.id, {})
    assert loaded_thread.metadata["workflow_id"] == "wf_ctx"


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
async def test_sqlite_store_load_threads_with_pagination(tmp_path: Path) -> None:
    """SQLite store supports cursor-based pagination for threads."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    for i in range(5):
        thread = ThreadMetadata(
            id=f"thr_{i}",
            created_at=datetime(2024, 1, i + 1, tzinfo=UTC),
            metadata={"index": i},
        )
        await store.save_thread(thread, context)

    page1 = await store.load_threads(limit=2, after=None, order="asc", context=context)
    assert len(page1.data) == 2
    assert page1.has_more is True
    assert page1.data[0].id == "thr_0"

    page2 = await store.load_threads(
        limit=2, after=page1.data[-1].id, order="asc", context=context
    )
    assert len(page2.data) == 2
    assert page2.data[0].id == "thr_2"


@pytest.mark.asyncio
async def test_sqlite_store_load_threads_descending(tmp_path: Path) -> None:
    """SQLite store supports descending order for threads."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    for i in range(3):
        thread = ThreadMetadata(
            id=f"thr_{i}",
            created_at=datetime(2024, 1, i + 1, tzinfo=UTC),
        )
        await store.save_thread(thread, context)

    page = await store.load_threads(limit=10, after=None, order="desc", context=context)
    assert page.data[0].id == "thr_2"
    assert page.data[-1].id == "thr_0"


@pytest.mark.asyncio
async def test_sqlite_store_load_thread_items_pagination(tmp_path: Path) -> None:
    """SQLite store supports cursor-based pagination for thread items."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}
    thread_id = "thr_items"

    thread = ThreadMetadata(id=thread_id, created_at=_timestamp())
    await store.save_thread(thread, context)

    for i in range(4):
        item = UserMessageItem(
            id=f"msg_{i}",
            thread_id=thread_id,
            created_at=datetime(2024, 1, 1, hour=i, tzinfo=UTC),
            content=[UserMessageTextContent(type="input_text", text=f"Message {i}")],
            attachments=[],
            quoted_text=None,
            inference_options=InferenceOptions(),
        )
        await store.add_thread_item(thread_id, item, context)

    page1 = await store.load_thread_items(
        thread_id, after=None, limit=2, order="asc", context=context
    )
    assert len(page1.data) == 2
    assert page1.has_more is True

    page2 = await store.load_thread_items(
        thread_id, after=page1.data[-1].id, limit=2, order="asc", context=context
    )
    assert len(page2.data) == 2
    assert page2.has_more is False


@pytest.mark.asyncio
async def test_sqlite_store_load_thread_items_descending(tmp_path: Path) -> None:
    """SQLite store supports descending order for thread items."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}
    thread_id = "thr_desc"

    thread = ThreadMetadata(id=thread_id, created_at=_timestamp())
    await store.save_thread(thread, context)

    for i in range(3):
        item = UserMessageItem(
            id=f"msg_{i}",
            thread_id=thread_id,
            created_at=datetime(2024, 1, 1, hour=i, tzinfo=UTC),
            content=[UserMessageTextContent(type="input_text", text=f"Message {i}")],
            attachments=[],
            quoted_text=None,
            inference_options=InferenceOptions(),
        )
        await store.add_thread_item(thread_id, item, context)

    page = await store.load_thread_items(
        thread_id, after=None, limit=10, order="desc", context=context
    )
    assert page.data[0].id == "msg_2"
    assert page.data[-1].id == "msg_0"


@pytest.mark.asyncio
async def test_sqlite_store_load_item_not_found(tmp_path: Path) -> None:
    """SQLite store raises NotFoundError for missing items."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    with pytest.raises(NotFoundError):
        await store.load_item("thr_missing", "msg_missing", context)


@pytest.mark.asyncio
async def test_sqlite_store_thread_not_found(tmp_path: Path) -> None:
    """SQLite store raises NotFoundError for missing threads."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    with pytest.raises(NotFoundError):
        await store.load_thread("thr_missing", context)


@pytest.mark.asyncio
async def test_sqlite_store_add_thread_item_wrong_thread(tmp_path: Path) -> None:
    """Add thread item should raise ValueError when thread_id mismatch."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    thread = ThreadMetadata(id="thr_correct", created_at=_timestamp())
    await store.save_thread(thread, context)

    item = UserMessageItem(
        id="msg_wrong",
        thread_id="thr_different",
        created_at=_timestamp(),
        content=[UserMessageTextContent(type="input_text", text="Test")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )

    with pytest.raises(ValueError, match="does not belong"):
        await store.add_thread_item("thr_correct", item, context)


@pytest.mark.asyncio
async def test_sqlite_store_save_item_update_existing(tmp_path: Path) -> None:
    """Save item should update an existing item."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    thread = ThreadMetadata(id="thr_update", created_at=_timestamp())
    await store.save_thread(thread, context)

    item = UserMessageItem(
        id="msg_update",
        thread_id=thread.id,
        created_at=_timestamp(),
        content=[UserMessageTextContent(type="input_text", text="Original")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await store.add_thread_item(thread.id, item, context)

    updated_item = UserMessageItem(
        id="msg_update",
        thread_id=thread.id,
        created_at=_timestamp(),
        content=[UserMessageTextContent(type="input_text", text="Updated")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await store.save_item(thread.id, updated_item, context)

    loaded = await store.load_item(thread.id, item.id, context)
    assert loaded.content[0].text == "Updated"


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


@pytest.mark.asyncio
async def test_sqlite_store_merge_metadata_no_request(tmp_path: Path) -> None:
    """Save thread should handle context without chatkit_request."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)

    thread = ThreadMetadata(
        id="thr_no_req",
        created_at=_timestamp(),
        metadata={"existing": "value"},
    )

    context: dict[str, object] = {"other_key": "other_value"}
    await store.save_thread(thread, context)

    loaded = await store.load_thread(thread.id, {})
    assert loaded.metadata["existing"] == "value"


@pytest.mark.asyncio
async def test_sqlite_store_merge_metadata_no_metadata_attr(tmp_path: Path) -> None:
    """Save thread should handle request without metadata attribute."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)

    request = SimpleNamespace(params="test")
    context: dict[str, object] = {"chatkit_request": request}

    thread = ThreadMetadata(
        id="thr_no_meta",
        created_at=_timestamp(),
        metadata={"existing": "value"},
    )

    await store.save_thread(thread, context)

    loaded = await store.load_thread(thread.id, {})
    assert loaded.metadata["existing"] == "value"


@pytest.mark.asyncio
async def test_sqlite_store_merge_metadata_empty_dict(tmp_path: Path) -> None:
    """Save thread should handle request with empty metadata dict."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)

    request = SimpleNamespace(metadata={})
    context: dict[str, object] = {"chatkit_request": request}

    thread = ThreadMetadata(
        id="thr_empty_meta",
        created_at=_timestamp(),
        metadata={"existing": "value"},
    )

    await store.save_thread(thread, context)

    loaded = await store.load_thread(thread.id, {})
    assert loaded.metadata["existing"] == "value"


@pytest.mark.asyncio
async def test_sqlite_store_infer_thread_id_from_context(tmp_path: Path) -> None:
    """Save attachment should infer thread_id from context."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)

    thread = ThreadMetadata(id="thr_infer", created_at=_timestamp())
    await store.save_thread(thread, {})

    params = SimpleNamespace(thread_id="thr_infer")
    request = SimpleNamespace(params=params)
    context: dict[str, object] = {"chatkit_request": request}

    attachment = FileAttachment(
        id="atc_infer",
        name="test.txt",
        mime_type="text/plain",
    )
    await store.save_attachment(attachment, context)

    loaded = await store.load_attachment(attachment.id, {})
    assert loaded.name == "test.txt"


@pytest.mark.asyncio
async def test_sqlite_store_load_threads_pagination_with_after_marker(
    tmp_path: Path,
) -> None:
    """Load threads should correctly handle pagination with after cursor."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    for i in range(5):
        thread = ThreadMetadata(
            id=f"thr_{i}",
            created_at=datetime(2024, 1, 1, hour=i, tzinfo=UTC),
        )
        await store.save_thread(thread, context)

    first_page = await store.load_threads(
        limit=2, after=None, order="asc", context=context
    )
    assert len(first_page.data) == 2
    assert first_page.has_more is True

    second_page = await store.load_threads(
        limit=2, after=first_page.data[-1].id, order="asc", context=context
    )
    assert len(second_page.data) == 2
    assert second_page.data[0].id != first_page.data[-1].id


@pytest.mark.asyncio
async def test_sqlite_store_load_thread_items_pagination_with_after(
    tmp_path: Path,
) -> None:
    """Load thread items should correctly handle pagination with after cursor."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}
    thread_id = "thr_paginate"

    thread = ThreadMetadata(id=thread_id, created_at=_timestamp())
    await store.save_thread(thread, context)

    for i in range(5):
        item = UserMessageItem(
            id=f"msg_{i}",
            thread_id=thread_id,
            created_at=datetime(2024, 1, 1, hour=i, tzinfo=UTC),
            content=[UserMessageTextContent(type="input_text", text=f"Message {i}")],
            attachments=[],
            quoted_text=None,
            inference_options=InferenceOptions(),
        )
        await store.add_thread_item(thread_id, item, context)

    first_page = await store.load_thread_items(
        thread_id, after=None, limit=2, order="asc", context=context
    )
    assert len(first_page.data) == 2
    assert first_page.has_more is True

    second_page = await store.load_thread_items(
        thread_id, after=first_page.data[-1].id, limit=2, order="asc", context=context
    )
    assert len(second_page.data) == 2
    assert second_page.data[0].id != first_page.data[-1].id


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
async def test_sqlite_store_naive_datetime_conversion(tmp_path: Path) -> None:
    """Store should handle naive datetime by adding UTC timezone."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    naive_dt = datetime(2024, 1, 1, 12, 0, 0)
    thread = ThreadMetadata(
        id="thr_naive",
        created_at=naive_dt,
    )

    await store.save_thread(thread, context)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT created_at FROM chat_threads WHERE id = ?", ("thr_naive",)
        )
        row = cursor.fetchone()
        assert row is not None
        assert "+00:00" in row[0] or "Z" in row[0] or row[0].endswith("+00:00")


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


@pytest.mark.asyncio
async def test_sqlite_store_already_initialized(tmp_path: Path) -> None:
    """Store should skip initialization when already initialized."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    thread = ThreadMetadata(id="thr_init", created_at=_timestamp())
    await store.save_thread(thread, context)

    assert store._initialized is True

    thread2 = ThreadMetadata(id="thr_init2", created_at=_timestamp())
    await store.save_thread(thread2, context)

    loaded = await store.load_thread("thr_init2", context)
    assert loaded.id == "thr_init2"


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
async def test_sqlite_store_load_threads_pagination_desc_with_after(
    tmp_path: Path,
) -> None:
    """Load threads descending should correctly handle pagination with after."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    for i in range(5):
        thread = ThreadMetadata(
            id=f"thr_{i}",
            created_at=datetime(2024, 1, 1, hour=i, tzinfo=UTC),
        )
        await store.save_thread(thread, context)

    first_page = await store.load_threads(
        limit=2, after=None, order="desc", context=context
    )
    assert len(first_page.data) == 2
    assert first_page.has_more is True

    second_page = await store.load_threads(
        limit=2, after=first_page.data[-1].id, order="desc", context=context
    )
    assert len(second_page.data) == 2
    assert second_page.data[0].id != first_page.data[-1].id


@pytest.mark.asyncio
async def test_sqlite_store_load_thread_items_pagination_desc_with_after(
    tmp_path: Path,
) -> None:
    """Load thread items descending should handle pagination with after."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}
    thread_id = "thr_desc_paginate"

    thread = ThreadMetadata(id=thread_id, created_at=_timestamp())
    await store.save_thread(thread, context)

    for i in range(5):
        item = UserMessageItem(
            id=f"msg_{i}",
            thread_id=thread_id,
            created_at=datetime(2024, 1, 1, hour=i, tzinfo=UTC),
            content=[UserMessageTextContent(type="input_text", text=f"Message {i}")],
            attachments=[],
            quoted_text=None,
            inference_options=InferenceOptions(),
        )
        await store.add_thread_item(thread_id, item, context)

    first_page = await store.load_thread_items(
        thread_id, after=None, limit=2, order="desc", context=context
    )
    assert len(first_page.data) == 2
    assert first_page.has_more is True

    second_page = await store.load_thread_items(
        thread_id, after=first_page.data[-1].id, limit=2, order="desc", context=context
    )
    assert len(second_page.data) == 2
    assert second_page.data[0].id != first_page.data[-1].id


@pytest.mark.asyncio
async def test_sqlite_store_load_threads_with_invalid_after(tmp_path: Path) -> None:
    """Load threads should handle invalid after cursor gracefully."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    for i in range(3):
        thread = ThreadMetadata(
            id=f"thr_{i}",
            created_at=datetime(2024, 1, 1, hour=i, tzinfo=UTC),
        )
        await store.save_thread(thread, context)

    page = await store.load_threads(
        limit=10, after="nonexistent_thread", order="asc", context=context
    )
    assert len(page.data) == 3


@pytest.mark.asyncio
async def test_sqlite_store_load_thread_items_with_invalid_after(
    tmp_path: Path,
) -> None:
    """Load thread items should handle invalid after cursor gracefully."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}
    thread_id = "thr_invalid_after"

    thread = ThreadMetadata(id=thread_id, created_at=_timestamp())
    await store.save_thread(thread, context)

    for i in range(3):
        item = UserMessageItem(
            id=f"msg_{i}",
            thread_id=thread_id,
            created_at=datetime(2024, 1, 1, hour=i, tzinfo=UTC),
            content=[UserMessageTextContent(type="input_text", text=f"Message {i}")],
            attachments=[],
            quoted_text=None,
            inference_options=InferenceOptions(),
        )
        await store.add_thread_item(thread_id, item, context)

    page = await store.load_thread_items(
        thread_id, after="nonexistent_item", limit=10, order="asc", context=context
    )
    assert len(page.data) == 3


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
async def test_sqlite_store_concurrent_initialization(tmp_path: Path) -> None:
    """Store should handle concurrent initialization attempts safely."""
    import asyncio

    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    async def save_thread_task(thread_id: str) -> None:
        thread = ThreadMetadata(id=thread_id, created_at=_timestamp())
        await store.save_thread(thread, context)

    await asyncio.gather(
        save_thread_task("thr_concurrent_1"),
        save_thread_task("thr_concurrent_2"),
        save_thread_task("thr_concurrent_3"),
    )

    thread1 = await store.load_thread("thr_concurrent_1", context)
    thread2 = await store.load_thread("thr_concurrent_2", context)
    thread3 = await store.load_thread("thr_concurrent_3", context)

    assert thread1.id == "thr_concurrent_1"
    assert thread2.id == "thr_concurrent_2"
    assert thread3.id == "thr_concurrent_3"


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


@pytest.mark.asyncio
async def test_sqlite_store_infer_thread_id_no_context(tmp_path: Path) -> None:
    """Infer thread ID should return None when context is missing."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)

    attachment = FileAttachment(
        id="atc_no_ctx",
        name="test.txt",
        mime_type="text/plain",
    )

    context: dict[str, object] = {}
    await store.save_attachment(attachment, context)

    loaded = await store.load_attachment(attachment.id, context)
    assert loaded.name == "test.txt"


@pytest.mark.asyncio
async def test_sqlite_store_infer_thread_id_no_params(tmp_path: Path) -> None:
    """Infer thread ID should handle request without params."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)

    request = SimpleNamespace()
    context: dict[str, object] = {"chatkit_request": request}

    attachment = FileAttachment(
        id="atc_no_params",
        name="test.txt",
        mime_type="text/plain",
    )

    await store.save_attachment(attachment, context)

    loaded = await store.load_attachment(attachment.id, context)
    assert loaded.name == "test.txt"


@pytest.mark.asyncio
async def test_sqlite_store_merge_metadata_non_dict_metadata(tmp_path: Path) -> None:
    """Save thread should handle request with non-dict metadata."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)

    request = SimpleNamespace(metadata="not a dict")
    context: dict[str, object] = {"chatkit_request": request}

    thread = ThreadMetadata(
        id="thr_non_dict_meta",
        created_at=_timestamp(),
        metadata={"existing": "value"},
    )

    await store.save_thread(thread, context)

    loaded = await store.load_thread(thread.id, {})
    assert loaded.metadata["existing"] == "value"


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
    # Payload with created_at as integer (not a string)
    item_payload = {
        "type": "user_message",
        "id": "msg_non_str",
        "thread_id": thread_id,
        "created_at": 1234567890,  # Not a string
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
    # Should use the created_at from the row, not the invalid payload value
    assert isinstance(loaded.created_at, datetime)
