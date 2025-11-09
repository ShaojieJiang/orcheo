"""Item-level tests for the in-memory ChatKit store."""

from __future__ import annotations
from datetime import UTC, datetime
import pytest
from chatkit.types import InferenceOptions, UserMessageItem, UserMessageTextContent
from orcheo_backend.app.chatkit import (
    ChatKitRequestContext,
    InMemoryChatKitStore,
)


def _build_user_item(thread_id: str, *, index: int) -> UserMessageItem:
    return UserMessageItem(
        id=f"msg_{index}",
        thread_id=thread_id,
        created_at=datetime(2024, 1, 1, hour=index, tzinfo=UTC),
        content=[UserMessageTextContent(type="input_text", text=f"Message {index}")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )


@pytest.mark.asyncio
async def test_in_memory_store_load_thread_items_pagination() -> None:
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}
    thread_id = "thr_items"

    items = [_build_user_item(thread_id, index=i) for i in range(4)]
    for item in items:
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
async def test_in_memory_store_load_thread_items_descending() -> None:
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}
    thread_id = "thr_desc"

    items = [_build_user_item(thread_id, index=i) for i in range(3)]
    for item in items:
        await store.add_thread_item(thread_id, item, context)

    page = await store.load_thread_items(
        thread_id, after=None, limit=10, order="desc", context=context
    )
    assert page.data[0].id == "msg_2"
    assert page.data[-1].id == "msg_0"


@pytest.mark.asyncio
async def test_in_memory_store_save_item() -> None:
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}
    thread_id = "thr_save"

    item = _build_user_item(thread_id, index=1)
    await store.save_item(thread_id, item, context)

    loaded = await store.load_item(thread_id, "msg_1", context)
    assert loaded.content[0].text == "Message 1"

    updated_item = UserMessageItem(
        id="msg_1",
        thread_id=thread_id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Updated")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await store.save_item(thread_id, updated_item, context)

    loaded_updated = await store.load_item(thread_id, "msg_1", context)
    assert loaded_updated.content[0].text == "Updated"


@pytest.mark.asyncio
async def test_in_memory_store_load_item_not_found() -> None:
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}

    from chatkit.store import NotFoundError

    with pytest.raises(NotFoundError):
        await store.load_item("thr_missing", "msg_missing", context)


@pytest.mark.asyncio
async def test_in_memory_store_delete_thread_item() -> None:
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}
    thread_id = "thr_delete"

    item = _build_user_item(thread_id, index=0)
    await store.add_thread_item(thread_id, item, context)

    await store.delete_thread_item(thread_id, item.id, context)

    page = await store.load_thread_items(
        thread_id, after=None, limit=10, order="asc", context=context
    )
    assert len(page.data) == 0


@pytest.mark.asyncio
async def test_in_memory_store_save_item_iterates_through_non_matching() -> None:
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}
    thread_id = "thr_iter"

    for i in range(3):
        await store.add_thread_item(
            thread_id,
            _build_user_item(thread_id, index=i),
            context,
        )

    new_item = UserMessageItem(
        id="msg_new",
        thread_id=thread_id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="New message")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await store.save_item(thread_id, new_item, context)

    loaded = await store.load_item(thread_id, "msg_new", context)
    assert loaded.content[0].text == "New message"


@pytest.mark.asyncio
async def test_in_memory_store_load_item_iterates_through_non_matching() -> None:
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}
    thread_id = "thr_search"

    for i in range(3):
        await store.add_thread_item(
            thread_id,
            _build_user_item(thread_id, index=i),
            context,
        )

    from chatkit.store import NotFoundError

    with pytest.raises(NotFoundError):
        await store.load_item(thread_id, "msg_nonexistent", context)
