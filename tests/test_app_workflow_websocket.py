"""Tests for the workflow websocket entrypoint."""

from unittest.mock import AsyncMock, patch
import pytest
from fastapi import WebSocket
from orcheo_backend.app import workflow_websocket
from orcheo_backend.app.history import InMemoryRunHistoryStore


@pytest.mark.asyncio
async def test_workflow_websocket_routes_requests() -> None:
    """Incoming messages trigger execute_workflow with the provided payloads."""

    mock_websocket = AsyncMock(spec=WebSocket)
    mock_websocket.receive_json.return_value = {
        "type": "run_workflow",
        "graph_config": {"nodes": []},
        "inputs": {"input": "test"},
        "execution_id": "test-execution",
    }

    with (
        patch("orcheo_backend.app.execute_workflow") as mock_execute,
        patch(
            "orcheo_backend.app._history_store_ref",
            {"store": InMemoryRunHistoryStore()},
        ),
    ):
        mock_execute.return_value = None
        await workflow_websocket(mock_websocket, "test-workflow")

    mock_websocket.accept.assert_called_once()
    mock_websocket.receive_json.assert_called_once()
    mock_execute.assert_called_once_with(
        "test-workflow",
        {"nodes": []},
        {"input": "test"},
        "test-execution",
        mock_websocket,
    )
    mock_websocket.close.assert_called_once()
