"""Thread item pagination tests for the SQLite ChatKit store."""

from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
import pytest
from chatkit.types import (
    InferenceOptions,
    ThreadMetadata,
    UserMessageItem,
    UserMessageTextContent,
)
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore


def _hour_timestamp(hour: int) -> datetime:
    return datetime(2024, 1, 1, hour=hour, tzinfo=UTC)


async def _add_items(
    store: SqliteChatKitStore,
    thread_id: str,
    context: dict[str, object],
    count: int,
) -> None:
    for i in range(count):
        item = UserMessageItem(
            id=f"msg_{i}",
            thread_id=thread_id,
            created_at=_hour_timestamp(i),
            content=[UserMessageTextContent(type="input_text", text=f"Message {i}")],
            attachments=[],
            quoted_text=None,
            inference_options=InferenceOptions(),
        )
        await store.add_thread_item(thread_id, item, context)


@pytest.mark.asyncio
async def test_sqlite_store_load_thread_items_pagination(tmp_path: Path) -> None:
    """SQLite store supports cursor-based pagination for thread items."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}
    thread_id = "thr_items"

    thread = ThreadMetadata(id=thread_id, created_at=datetime.now(tz=UTC))
    await store.save_thread(thread, context)

    await _add_items(store, thread_id, context, 4)

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

    thread = ThreadMetadata(id=thread_id, created_at=datetime.now(tz=UTC))
    await store.save_thread(thread, context)

    await _add_items(store, thread_id, context, 3)

    page = await store.load_thread_items(
        thread_id, after=None, limit=10, order="desc", context=context
    )
    assert page.data[0].id == "msg_2"
    assert page.data[-1].id == "msg_0"


@pytest.mark.asyncio
async def test_sqlite_store_load_thread_items_pagination_with_after(
    tmp_path: Path,
) -> None:
    """Load thread items should correctly handle pagination with after cursor."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}
    thread_id = "thr_paginate"

    thread = ThreadMetadata(id=thread_id, created_at=datetime.now(tz=UTC))
    await store.save_thread(thread, context)

    await _add_items(store, thread_id, context, 5)

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
async def test_sqlite_store_load_thread_items_pagination_desc_with_after(
    tmp_path: Path,
) -> None:
    """Load thread items descending should handle pagination with after."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}
    thread_id = "thr_desc_paginate"

    thread = ThreadMetadata(id=thread_id, created_at=datetime.now(tz=UTC))
    await store.save_thread(thread, context)

    await _add_items(store, thread_id, context, 5)

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
async def test_sqlite_store_load_thread_items_with_invalid_after(
    tmp_path: Path,
) -> None:
    """Load thread items should handle invalid after cursor gracefully."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}
    thread_id = "thr_invalid_after"

    thread = ThreadMetadata(id=thread_id, created_at=datetime.now(tz=UTC))
    await store.save_thread(thread, context)

    await _add_items(store, thread_id, context, 3)

    page = await store.load_thread_items(
        thread_id, after="nonexistent_item", limit=10, order="asc", context=context
    )
    assert len(page.data) == 3
