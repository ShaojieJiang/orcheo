"""ChatKit store retrieval and cleanup tests for orcheo_backend.app."""

from __future__ import annotations
import asyncio
from typing import Any
from unittest.mock import Mock, patch
import pytest
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore
from tests.backend.api.shared import backend_app


def test_get_chatkit_store_when_no_server() -> None:
    """_get_chatkit_store returns None when server missing."""
    with patch.dict(backend_app._chatkit_server_ref, {"server": None}):
        result = backend_app._get_chatkit_store()
        assert result is None


def test_get_chatkit_store_when_not_sqlite_store() -> None:
    """_get_chatkit_store ignores stores that are not SqliteChatKitStore."""
    mock_server = Mock()
    mock_server.store = Mock()  # Not a SqliteChatKitStore
    with patch.dict(backend_app._chatkit_server_ref, {"server": mock_server}):
        result = backend_app._get_chatkit_store()
        assert result is None


def test_get_chatkit_store_when_no_store_attr() -> None:
    """_get_chatkit_store handles servers without store attribute."""
    mock_server = Mock(spec=[])  # No store attribute
    with patch.dict(backend_app._chatkit_server_ref, {"server": mock_server}):
        result = backend_app._get_chatkit_store()
        assert result is None


@pytest.mark.asyncio
async def test_ensure_chatkit_cleanup_task_when_no_store() -> None:
    """_ensure_chatkit_cleanup_task skips when no store."""
    with patch.dict(backend_app._chatkit_cleanup_task, {"task": None}):
        with patch.object(backend_app, "_get_chatkit_store", return_value=None):
            await backend_app._ensure_chatkit_cleanup_task()
            assert backend_app._chatkit_cleanup_task["task"] is None


@pytest.mark.asyncio
async def test_cancel_chatkit_cleanup_task_when_no_task() -> None:
    """_cancel_chatkit_cleanup_task exits cleanly when nothing running."""
    with patch.dict(backend_app._chatkit_cleanup_task, {"task": None}):
        await backend_app._cancel_chatkit_cleanup_task()
        assert backend_app._chatkit_cleanup_task["task"] is None


@pytest.mark.asyncio
async def test_chatkit_cleanup_task_with_valid_store(tmp_path: Any) -> None:
    """Cleanup task spins up when valid SqliteChatKitStore is available."""
    db_path = tmp_path / "chatkit_test.sqlite"
    store = SqliteChatKitStore(str(db_path))

    async def mock_prune(*args: Any, **kwargs: Any) -> int:
        return 0

    store.prune_threads_older_than = mock_prune  # type: ignore[method-assign]

    mock_server = Mock()
    mock_server.store = store

    with patch.dict(backend_app._chatkit_server_ref, {"server": mock_server}):
        with patch.dict(backend_app._chatkit_cleanup_task, {"task": None}):
            with patch.object(backend_app, "_CHATKIT_CLEANUP_INTERVAL_SECONDS", 0.05):
                await backend_app._ensure_chatkit_cleanup_task()
                task = backend_app._chatkit_cleanup_task["task"]
                assert task is not None

                await asyncio.sleep(0.15)

                await backend_app._cancel_chatkit_cleanup_task()
                assert backend_app._chatkit_cleanup_task["task"] is None
