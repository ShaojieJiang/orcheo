"""Websocket resilience helpers and router behaviors."""

from __future__ import annotations
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import WebSocket, WebSocketDisconnect
from orcheo_backend.app import workflow_websocket
from orcheo_backend.app.routers import websocket as websocket_routes


@pytest.mark.asyncio
async def test_safe_send_error_payload_ignores_disconnect() -> None:
    """Websocket disconnections should be swallowed when sending errors."""

    websocket = AsyncMock(spec=WebSocket)
    websocket.send_json.side_effect = WebSocketDisconnect()

    await websocket_routes._safe_send_error_payload(websocket, {"status": "error"})
    websocket.send_json.assert_awaited_once()


@pytest.mark.asyncio
async def test_safe_send_error_payload_ignores_closed_connection() -> None:
    """Runtime errors after close should be ignored."""

    websocket = AsyncMock(spec=WebSocket)
    websocket.send_json.side_effect = RuntimeError(
        websocket_routes._CANNOT_SEND_AFTER_CLOSE
    )

    await websocket_routes._safe_send_error_payload(websocket, {"status": "error"})
    websocket.send_json.assert_awaited_once()


@pytest.mark.asyncio
async def test_safe_close_websocket_ignores_disconnect_and_closed() -> None:
    """Closing an already-closed websocket is a no-op."""

    websocket = AsyncMock(spec=WebSocket)
    websocket.close.side_effect = WebSocketDisconnect()

    await websocket_routes._safe_close_websocket(websocket)
    websocket.close.assert_awaited_once()

    websocket.close.reset_mock()
    websocket.close.side_effect = RuntimeError(
        websocket_routes._CANNOT_SEND_AFTER_CLOSE
    )
    await websocket_routes._safe_close_websocket(websocket)
    websocket.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_safe_send_error_payload_propagates_unexpected_runtime_error() -> None:
    """Unexpected runtime errors should bubble up instead of being swallowed."""

    websocket = AsyncMock(spec=WebSocket)
    websocket.send_json.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await websocket_routes._safe_send_error_payload(websocket, {"status": "error"})


@pytest.mark.asyncio
async def test_safe_close_websocket_propagates_unexpected_runtime_error() -> None:
    """Close errors other than the known constant should still be raised."""

    websocket = AsyncMock(spec=WebSocket)
    websocket.close.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await websocket_routes._safe_close_websocket(websocket)


@pytest.mark.asyncio
async def test_workflow_websocket_handles_client_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A disconnect while waiting for a message should simply close the socket."""

    mock_websocket = AsyncMock(spec=WebSocket)
    mock_websocket.receive_json.side_effect = WebSocketDisconnect()
    mock_websocket.state = SimpleNamespace()

    backend_app_module = importlib.import_module("orcheo_backend.app")
    monkeypatch.setattr(
        backend_app_module,
        "authenticate_websocket",
        AsyncMock(return_value={"sub": "tester"}),
    )
    close_mock = AsyncMock()
    monkeypatch.setattr(
        websocket_routes,
        "_safe_close_websocket",
        close_mock,
    )

    await workflow_websocket(mock_websocket, "workflow-id")

    mock_websocket.accept.assert_awaited_once()
    close_mock.assert_awaited_once_with(mock_websocket)
