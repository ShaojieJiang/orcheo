"""Tests for the FastAPI backend module."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import WebSocket
from orcheo_backend.app import execute_workflow, get_repository, workflow_websocket


@pytest.mark.asyncio
async def test_execute_workflow():
    # Mock dependencies
    mock_websocket = AsyncMock(spec=WebSocket)
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

    mock_checkpointer = object()

    @asynccontextmanager
    async def fake_checkpointer(_settings):
        yield mock_checkpointer

    with (
        patch("orcheo_backend.app.create_checkpointer", fake_checkpointer),
        patch("orcheo_backend.app.build_graph", return_value=mock_graph),
    ):
        await execute_workflow(
            workflow_id, graph_config, inputs, execution_id, mock_websocket
        )

    mock_graph.compile.assert_called_once_with(checkpointer=mock_checkpointer)
    mock_websocket.send_json.assert_any_call(steps[0])
    mock_websocket.send_json.assert_any_call(steps[1])


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
    with patch("orcheo_backend.app.execute_workflow") as mock_execute:
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


def test_get_repository_returns_singleton() -> None:
    """The module-level repository accessor returns a singleton instance."""

    first = get_repository()
    second = get_repository()
    assert first is second
