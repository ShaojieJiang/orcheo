"""Extra ChatKit coverage tests for orcheo_backend.app."""

from __future__ import annotations
import asyncio
import importlib
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from orcheo.models import AesGcmCredentialCipher
from orcheo.vault import InMemoryCredentialVault
from orcheo.vault.oauth import OAuthCredentialService
from orcheo_backend.app import create_app
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore
from orcheo_backend.app.repository import InMemoryWorkflowRepository


backend_app = importlib.import_module("orcheo_backend.app")
factory_module = importlib.import_module("orcheo_backend.app.factory")


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


@pytest.mark.asyncio
async def test_chatkit_gateway_validation_error(api_client: TestClient) -> None:
    """chatkit_gateway rejects malformed payloads."""
    response = api_client.post(
        "/api/chatkit",
        json={"invalid": "payload"},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Invalid ChatKit payload" in detail["message"]
    assert "errors" in detail


@pytest.mark.asyncio
async def test_chatkit_gateway_streaming_response(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """chatkit_gateway handles streaming responses."""
    from chatkit.server import StreamingResult

    async def mock_stream() -> AsyncIterator[bytes]:
        yield b"data: test\n\n"

    mock_result = StreamingResult(mock_stream())

    async def mock_process(payload: bytes, context: Any) -> StreamingResult:
        return mock_result

    mock_server = AsyncMock()
    mock_server.process = mock_process

    mock_adapter = Mock()
    mock_adapter.validate_json.return_value = {"action": "chat"}

    monkeypatch.setattr(backend_app, "get_chatkit_server", lambda: mock_server)
    monkeypatch.setattr(backend_app, "TypeAdapter", lambda x: mock_adapter)

    response = api_client.post(
        "/api/chatkit",
        json={"test": "payload"},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_chatkit_gateway_json_response_with_callable(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """chatkit_gateway supports callables returning JSON responses."""

    class MockResult:
        def __init__(self) -> None:
            self.json = lambda: {"result": "success"}
            self.status_code = 200
            self.headers = {"x-custom": "header"}
            self.media_type = "application/json"

    async def mock_process(payload: bytes, context: Any) -> MockResult:
        return MockResult()

    mock_server = AsyncMock()
    mock_server.process = mock_process

    mock_adapter = Mock()
    mock_adapter.validate_json.return_value = {"action": "chat"}

    monkeypatch.setattr(backend_app, "get_chatkit_server", lambda: mock_server)
    monkeypatch.setattr(backend_app, "TypeAdapter", lambda x: mock_adapter)

    response = api_client.post("/api/chatkit", json={"test": "payload"})

    assert response.status_code == 200
    assert response.json() == {"result": "success"}


@pytest.mark.asyncio
async def test_chatkit_gateway_json_response_with_bytes(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """chatkit_gateway supports responses returning bytes."""

    class MockResult:
        def __init__(self) -> None:
            self.json = b"binary-data"
            self.status_code = 200
            self.headers = None
            self.media_type = "application/octet-stream"

    async def mock_process(payload: bytes, context: Any) -> MockResult:
        return MockResult()

    mock_server = AsyncMock()
    mock_server.process = mock_process

    mock_adapter = Mock()
    mock_adapter.validate_json.return_value = {"action": "chat"}

    monkeypatch.setattr(backend_app, "get_chatkit_server", lambda: mock_server)
    monkeypatch.setattr(backend_app, "TypeAdapter", lambda x: mock_adapter)

    response = api_client.post("/api/chatkit", json={"test": "payload"})

    assert response.status_code == 200
    assert response.content == b"binary-data"


@pytest.mark.asyncio
async def test_chatkit_gateway_json_response_with_string(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """chatkit_gateway supports string payloads."""

    class MockResult:
        def __init__(self) -> None:
            self.json = "text response"
            self.status_code = 200
            self.headers = [("x-custom", "value")]
            self.media_type = "text/plain"

    async def mock_process(payload: bytes, context: Any) -> MockResult:
        return MockResult()

    mock_server = AsyncMock()
    mock_server.process = mock_process

    mock_adapter = Mock()
    mock_adapter.validate_json.return_value = {"action": "chat"}

    monkeypatch.setattr(backend_app, "get_chatkit_server", lambda: mock_server)
    monkeypatch.setattr(backend_app, "TypeAdapter", lambda x: mock_adapter)

    response = api_client.post("/api/chatkit", json={"test": "payload"})

    assert response.status_code == 200
    assert response.text == "text response"


@pytest.mark.asyncio
async def test_chatkit_gateway_dict_response(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """chatkit_gateway handles raw dict responses."""

    async def mock_process(payload: bytes, context: Any) -> dict[str, str]:
        return {"status": "ok"}

    mock_server = AsyncMock()
    mock_server.process = mock_process

    mock_adapter = Mock()
    mock_adapter.validate_json.return_value = {"action": "chat"}

    monkeypatch.setattr(backend_app, "get_chatkit_server", lambda: mock_server)
    monkeypatch.setattr(backend_app, "TypeAdapter", lambda x: mock_adapter)

    response = api_client.post("/api/chatkit", json={"test": "payload"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_app_startup_exception_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Startup handler swallows HTTPException from get_chatkit_server."""

    def mock_get_chatkit_server() -> None:
        raise HTTPException(status_code=503, detail="ChatKit not configured")

    monkeypatch.setattr(backend_app, "get_chatkit_server", mock_get_chatkit_server)
    monkeypatch.setattr(
        factory_module,
        "get_chatkit_server",
        mock_get_chatkit_server,
    )

    cipher = AesGcmCredentialCipher(key="test-key")
    vault = InMemoryCredentialVault(cipher=cipher)
    service = OAuthCredentialService(vault, token_ttl_seconds=600, providers={})
    repository = InMemoryWorkflowRepository(credential_service=service)

    app = create_app(repository, credential_service=service)

    with TestClient(app) as client:
        assert client is not None
