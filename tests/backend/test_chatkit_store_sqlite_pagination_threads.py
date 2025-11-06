"""Thread pagination tests for the SQLite ChatKit store."""

from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
import pytest
from chatkit.types import ThreadMetadata
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore


def _timestamp(hour: int) -> datetime:
    return datetime(2024, 1, 1, hour=hour, tzinfo=UTC)


@pytest.mark.asyncio
async def test_sqlite_store_load_threads_with_pagination(tmp_path: Path) -> None:
    """SQLite store supports cursor-based pagination for threads."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    for i in range(5):
        thread = ThreadMetadata(
            id=f"thr_{i}",
            created_at=_timestamp(i + 1),
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
            created_at=_timestamp(i + 1),
        )
        await store.save_thread(thread, context)

    page = await store.load_threads(limit=10, after=None, order="desc", context=context)
    assert page.data[0].id == "thr_2"
    assert page.data[-1].id == "thr_0"


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
            created_at=_timestamp(i),
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
            created_at=_timestamp(i),
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
async def test_sqlite_store_load_threads_with_invalid_after(tmp_path: Path) -> None:
    """Load threads should handle invalid after cursor gracefully."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)
    context: dict[str, object] = {}

    for i in range(3):
        thread = ThreadMetadata(
            id=f"thr_{i}",
            created_at=_timestamp(i),
        )
        await store.save_thread(thread, context)

    page = await store.load_threads(
        limit=10, after="nonexistent_thread", order="asc", context=context
    )
    assert len(page.data) == 3
