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
