"""Tests for the FastAPI backend module."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient
from orcheo_backend.app import (
    create_app,
    execute_workflow,
    get_repository,
    workflow_websocket,
)
from orcheo_backend.app.history import InMemoryRunHistoryStore
from orcheo_backend.app.repository import InMemoryWorkflowRepository


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

    history_store = InMemoryRunHistoryStore()

    with (
        patch("orcheo_backend.app.create_checkpointer", fake_checkpointer),
        patch("orcheo_backend.app.build_graph", return_value=mock_graph),
        patch("orcheo_backend.app._history_store_ref", {"store": history_store}),
    ):
        await execute_workflow(
            workflow_id, graph_config, inputs, execution_id, mock_websocket
        )

    mock_graph.compile.assert_called_once_with(checkpointer=mock_checkpointer)
    mock_websocket.send_json.assert_any_call(steps[0])
    mock_websocket.send_json.assert_any_call(steps[1])

    history = await history_store.get_history(execution_id)
    assert history.status == "completed"
    assert [step.payload for step in history.steps[:-1]] == steps
    assert history.steps[-1].payload == {"status": "completed"}


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
    with (
        patch("orcheo_backend.app.execute_workflow") as mock_execute,
        patch(
            "orcheo_backend.app._history_store_ref",
            {"store": InMemoryRunHistoryStore()},
        ),
    ):
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


def test_create_app_allows_dependency_override() -> None:
    """Passing a repository instance wires it into FastAPI dependency overrides."""

    repository = InMemoryWorkflowRepository()
    app = create_app(repository)

    override = app.dependency_overrides[get_repository]
    assert override() is repository


def test_execution_history_endpoints_return_steps() -> None:
    """Execution history endpoints expose stored replay data."""

    repository = InMemoryWorkflowRepository()
    history_store = InMemoryRunHistoryStore()

    execution_id = "exec-123"

    async def seed_history() -> None:
        await history_store.start_run(
            workflow_id="wf-1", execution_id=execution_id, inputs={"foo": "bar"}
        )
        await history_store.append_step(execution_id, {"node": "first"})
        await history_store.append_step(execution_id, {"node": "second"})
        await history_store.append_step(execution_id, {"status": "completed"})
        await history_store.mark_completed(execution_id)

    asyncio.run(seed_history())

    app = create_app(repository, history_store=history_store)
    client = TestClient(app)

    history_response = client.get(f"/api/executions/{execution_id}/history")
    assert history_response.status_code == 200
    history = history_response.json()
    assert history["execution_id"] == execution_id
    assert history["status"] == "completed"
    assert len(history["steps"]) == 3
    assert history["steps"][0]["payload"] == {"node": "first"}

    replay_response = client.post(
        f"/api/executions/{execution_id}/replay", json={"from_step": 1}
    )
    assert replay_response.status_code == 200
    replay = replay_response.json()
    assert len(replay["steps"]) == 2
    assert replay["steps"][0]["index"] == 1
    assert replay["steps"][0]["payload"] == {"node": "second"}
