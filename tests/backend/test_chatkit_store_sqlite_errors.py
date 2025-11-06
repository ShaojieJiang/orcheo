"""Error-handling tests for the SQLite ChatKit store."""

from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
import pytest
from chatkit.store import NotFoundError
from chatkit.types import (
    InferenceOptions,
    ThreadMetadata,
    UserMessageItem,
    UserMessageTextContent,
)
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore


def _timestamp() -> datetime:
    return datetime.now(tz=UTC)


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
