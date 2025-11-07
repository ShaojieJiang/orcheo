"""Thread-level tests for the in-memory ChatKit store."""

from __future__ import annotations
from datetime import UTC, datetime
import pytest
from chatkit.types import ThreadMetadata
from orcheo_backend.app.chatkit_service import (
    ChatKitRequestContext,
    InMemoryChatKitStore,
)


@pytest.mark.asyncio
async def test_in_memory_store_load_threads_pagination() -> None:
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}

    threads = [
        ThreadMetadata(
            id=f"thr_{i}",
            created_at=datetime(2024, 1, i + 1, tzinfo=UTC),
            metadata={"index": i},
        )
        for i in range(5)
    ]
    for thread in threads:
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
async def test_in_memory_store_load_threads_descending() -> None:
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}

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
async def test_in_memory_store_delete_thread() -> None:
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}

    thread = ThreadMetadata(id="thr_delete", created_at=datetime.now(UTC))
    await store.save_thread(thread, context)

    await store.delete_thread("thr_delete", context)

    from chatkit.store import NotFoundError

    with pytest.raises(NotFoundError):
        await store.load_thread("thr_delete", context)


@pytest.mark.asyncio
async def test_in_memory_store_attachment_methods_not_implemented() -> None:
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}

    from chatkit.types import FileAttachment

    attachment = FileAttachment(id="atc_1", name="test.txt", mime_type="text/plain")

    with pytest.raises(NotImplementedError):
        await store.save_attachment(attachment, context)

    with pytest.raises(NotImplementedError):
        await store.load_attachment("atc_1", context)

    with pytest.raises(NotImplementedError):
        await store.delete_attachment("atc_1", context)


@pytest.mark.asyncio
async def test_in_memory_store_merge_metadata_from_context() -> None:
    store = InMemoryChatKitStore()

    class FakeRequest:
        metadata = {"workflow_id": "wf_123", "extra": "data"}

    context: ChatKitRequestContext = {
        "chatkit_request": FakeRequest()  # type: ignore[typeddict-item]
    }

    thread = ThreadMetadata(
        id="thr_merge",
        created_at=datetime.now(UTC),
        metadata={"existing": "value"},
    )
    await store.save_thread(thread, context)

    assert thread.metadata["workflow_id"] == "wf_123"
    assert thread.metadata["existing"] == "value"


@pytest.mark.asyncio
async def test_in_memory_store_merge_metadata_without_request() -> None:
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}

    thread = ThreadMetadata(
        id="thr_no_request",
        created_at=datetime.now(UTC),
        metadata={"existing": "value"},
    )
    await store.save_thread(thread, context)

    loaded = await store.load_thread("thr_no_request", context)
    assert loaded.metadata["existing"] == "value"
