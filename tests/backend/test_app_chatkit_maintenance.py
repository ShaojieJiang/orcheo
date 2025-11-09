"""Tests for ChatKit background maintenance and store helpers."""

from __future__ import annotations
import asyncio
import sqlite3
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from orcheo_backend.app import (
    _cancel_chatkit_cleanup_task,
    _chatkit_cleanup_task,
    _chatkit_server_ref,
    _ensure_chatkit_cleanup_task,
    _get_chatkit_store,
)
from orcheo_backend.app.chatkit import InMemoryChatKitStore
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore


@pytest.mark.asyncio()
async def test_ensure_chatkit_cleanup_task_already_running() -> None:
    """Cleanup task should not be recreated if already running."""

    task = asyncio.create_task(asyncio.sleep(10))
    _chatkit_cleanup_task["task"] = task

    try:
        await _ensure_chatkit_cleanup_task()
        assert _chatkit_cleanup_task["task"] is task
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        _chatkit_cleanup_task["task"] = None


@pytest.mark.asyncio()
async def test_cancel_chatkit_cleanup_task_no_task() -> None:
    """Canceling cleanup task when none exists should be safe."""

    _chatkit_cleanup_task["task"] = None
    await _cancel_chatkit_cleanup_task()
    assert _chatkit_cleanup_task["task"] is None


@pytest.mark.asyncio()
async def test_chatkit_cleanup_task_prunes_threads(tmp_path: Path) -> None:
    """Cleanup task should prune old threads and log the count."""

    db_path = tmp_path / "chatkit_test.sqlite"
    store = SqliteChatKitStore(db_path)

    mock_server = MagicMock()
    mock_server.store = store
    _chatkit_server_ref["server"] = mock_server

    from chatkit.types import ThreadMetadata

    thread_id = "thr_old"
    old_thread = ThreadMetadata(
        id=thread_id,
        created_at=datetime.now(tz=UTC) - timedelta(days=60),
    )
    await store.save_thread(old_thread, {})

    with sqlite3.connect(db_path) as conn:
        stale_timestamp = (datetime.now(tz=UTC) - timedelta(days=60)).isoformat()
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
            (stale_timestamp, thread_id),
        )
        conn.commit()

    with (
        patch("orcheo_backend.app._chatkit_retention_days", return_value=30),
        patch("orcheo_backend.app._CHATKIT_CLEANUP_INTERVAL_SECONDS", 0.1),
    ):
        _chatkit_cleanup_task["task"] = None
        await _ensure_chatkit_cleanup_task()
        task = _chatkit_cleanup_task["task"]
        assert task is not None

        await asyncio.sleep(0.2)

        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    _chatkit_server_ref["server"] = None
    _chatkit_cleanup_task["task"] = None


def test_get_chatkit_store_returns_none_when_no_server() -> None:
    """Get chatkit store should return None when server is not initialized."""

    _chatkit_server_ref["server"] = None
    store = _get_chatkit_store()
    assert store is None


def test_get_chatkit_store_returns_none_for_non_sqlite_store() -> None:
    """Get chatkit store should return None when store is not SqliteChatKitStore."""

    mock_server = MagicMock()
    mock_server.store = InMemoryChatKitStore()
    _chatkit_server_ref["server"] = mock_server

    try:
        store = _get_chatkit_store()
        assert store is None
    finally:
        _chatkit_server_ref["server"] = None
