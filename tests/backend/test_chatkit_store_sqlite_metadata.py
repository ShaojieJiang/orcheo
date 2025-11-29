"""Metadata handling and attachment inference tests for the SQLite ChatKit store."""

from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
import pytest
from chatkit.types import FileAttachment, ThreadMetadata
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore


def _timestamp() -> datetime:
    return datetime.now(tz=UTC)


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
async def test_sqlite_store_persists_storage_path(tmp_path: Path) -> None:
    """Save attachment should persist storage_path for cleanup and retrieval."""
    db_path = tmp_path / "store.sqlite"
    store = SqliteChatKitStore(db_path)

    attachment = FileAttachment(
        id="atc_path",
        name="file.txt",
        mime_type="text/plain",
    )
    storage_path = tmp_path / "uploads" / "atc_path_file.txt"

    await store.save_attachment(
        attachment,
        context={},
        storage_path=str(storage_path),
    )

    async with store._connection() as conn:  # type: ignore[attr-defined]  # noqa: SLF001
        cursor = await conn.execute(
            "SELECT storage_path FROM chat_attachments WHERE id = ?",
            (attachment.id,),
        )
        row = await cursor.fetchone()

    assert row is not None
    assert row["storage_path"] == str(storage_path)
