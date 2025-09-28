"""Tests for main module."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import WebSocket
from orcheo.main import execute_workflow, workflow_websocket


class AsyncIteratorMock:
    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


@pytest.mark.asyncio
async def test_execute_workflow():
    # Mock dependencies
    mock_websocket = AsyncMock(spec=WebSocket)
    mock_conn = AsyncMock()
    mock_graph = MagicMock()

    # Test data
    workflow_id = "test-workflow"
    graph_config = {"nodes": []}
    inputs = {"input": "test"}
    execution_id = "test-execution"

    # Mock graph compilation
    steps = [
        {"status": "running", "data": "test"},
        {"status": "completed", "data": "done"},
    ]

    async def mock_astream(*args, **kwargs):
        for step in steps:
            yield step

    mock_compiled_graph = MagicMock()
    mock_compiled_graph.astream = mock_astream
    mock_graph.compile.return_value = mock_compiled_graph

    # Mock context managers
    mock_conn.__aenter__.return_value = mock_conn
    mock_conn.__aexit__.return_value = None

    with (
        patch("aiosqlite.connect", return_value=mock_conn),
        patch("orcheo.main.build_graph", return_value=mock_graph),
    ):
        await execute_workflow(
            workflow_id, graph_config, inputs, execution_id, mock_websocket
        )


@pytest.mark.asyncio
async def test_workflow_websocket():
    # Mock dependencies
    mock_websocket = AsyncMock(spec=WebSocket)
    mock_websocket.receive_json.return_value = {
        "type": "run_workflow",
        "graph_config": {"nodes": []},
        "inputs": {"input": "test"},
        "execution_id": "test-execution",
    }

    # Mock execute_workflow
    with patch("orcheo.main.execute_workflow") as mock_execute:
        mock_execute.return_value = None
        await workflow_websocket(mock_websocket, "test-workflow")

    # Verify websocket interactions
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
