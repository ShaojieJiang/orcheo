"""Tests for the FastAPI backend module."""

import asyncio
import textwrap
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException, WebSocket, status
from fastapi.testclient import TestClient
from orcheo.graph.ingestion import LANGGRAPH_SCRIPT_FORMAT
from orcheo_backend.app import (
    create_app,
    execute_workflow,
    get_repository,
    ingest_workflow_version,
    workflow_websocket,
)
from orcheo_backend.app.history import InMemoryRunHistoryStore
from orcheo_backend.app.repository import (
    InMemoryWorkflowRepository,
    WorkflowNotFoundError,
)
from orcheo_backend.app.schemas import WorkflowVersionIngestRequest


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
async def test_execute_workflow_langgraph_script_uses_raw_inputs() -> None:
    """LangGraph script executions pass the incoming inputs unchanged."""

    mock_websocket = AsyncMock(spec=WebSocket)
    mock_graph = MagicMock()

    graph_config = {"format": LANGGRAPH_SCRIPT_FORMAT}
    inputs: dict[str, str] = {"input": "raw"}
    execution_id = "script-exec"

    steps = [{"status": "completed"}]
    captured_state: Any | None = None

    async def mock_astream(state: Any, *args: Any, **kwargs: Any):
        nonlocal captured_state
        captured_state = state
        for step in steps:
            yield step

    mock_compiled_graph = MagicMock()
    mock_compiled_graph.astream = mock_astream
    mock_graph.compile.return_value = mock_compiled_graph

    @asynccontextmanager
    async def fake_checkpointer(_settings):
        yield object()

    history_store = InMemoryRunHistoryStore()

    with (
        patch("orcheo_backend.app.create_checkpointer", fake_checkpointer),
        patch("orcheo_backend.app.build_graph", return_value=mock_graph),
        patch("orcheo_backend.app._history_store_ref", {"store": history_store}),
    ):
        await execute_workflow(
            "langgraph-workflow",
            graph_config,
            inputs,
            execution_id,
            mock_websocket,
        )

    assert captured_state is inputs

    history = await history_store.get_history(execution_id)
    assert history.inputs == inputs
    assert history.steps[-1].payload == {"status": "completed"}


@pytest.mark.asyncio
async def test_execute_workflow_failure_records_error() -> None:
    """Failures during execution are captured within the history store."""

    mock_websocket = AsyncMock(spec=WebSocket)
    mock_graph = MagicMock()

    class _FailingStream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise RuntimeError("boom")

    def failing_astream(*args, **kwargs):
        return _FailingStream()

    mock_compiled_graph = MagicMock()
    mock_compiled_graph.astream = failing_astream
    mock_graph.compile.return_value = mock_compiled_graph

    @asynccontextmanager
    async def fake_checkpointer(_settings):
        yield object()

    history_store = InMemoryRunHistoryStore()

    with (
        patch("orcheo_backend.app.create_checkpointer", fake_checkpointer),
        patch("orcheo_backend.app.build_graph", return_value=mock_graph),
        patch("orcheo_backend.app._history_store_ref", {"store": history_store}),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            await execute_workflow(
                "wf",
                {"nodes": []},
                {"input": "data"},
                "exec-1",
                mock_websocket,
            )

    history = await history_store.get_history("exec-1")
    assert history.status == "error"
    assert history.error == "boom"
    assert history.steps[-1].payload == {"status": "error", "error": "boom"}


@pytest.mark.asyncio
async def test_execute_workflow_cancelled_records_reason() -> None:
    """Cancellations propagate the reason and update execution history."""

    mock_websocket = AsyncMock(spec=WebSocket)
    mock_graph = MagicMock()
    cancellation_reason = "client requested stop"

    class _CancellingStream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise asyncio.CancelledError(cancellation_reason)

    def cancelling_astream(*args, **kwargs):
        return _CancellingStream()

    mock_compiled_graph = MagicMock()
    mock_compiled_graph.astream = cancelling_astream
    mock_graph.compile.return_value = mock_compiled_graph

    @asynccontextmanager
    async def fake_checkpointer(_settings):
        yield object()

    history_store = InMemoryRunHistoryStore()

    with (
        patch("orcheo_backend.app.create_checkpointer", fake_checkpointer),
        patch("orcheo_backend.app.build_graph", return_value=mock_graph),
        patch("orcheo_backend.app._history_store_ref", {"store": history_store}),
    ):
        with pytest.raises(asyncio.CancelledError):
            await execute_workflow(
                "wf-cancel",
                {"nodes": []},
                {},
                "exec-cancel",
                mock_websocket,
            )

    history = await history_store.get_history("exec-cancel")
    assert history.status == "cancelled"
    assert history.error == cancellation_reason
    assert len(history.steps) == 1
    assert history.steps[0].payload == {
        "status": "cancelled",
        "reason": cancellation_reason,
    }


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


def test_ingest_workflow_version_endpoint_creates_version() -> None:
    """LangGraph scripts can be submitted to create workflow versions."""

    repository = InMemoryWorkflowRepository()
    workflow = asyncio.run(
        repository.create_workflow(
            name="LangGraph", slug=None, description=None, tags=[], actor="tester"
        )
    )

    app = create_app(repository)
    client = TestClient(app)

    script = textwrap.dedent(
        """
        from langgraph.graph import StateGraph
        from orcheo.graph.state import State

        def build_graph():
            graph = StateGraph(State)
            graph.add_node("noop", lambda state: state)
            graph.set_entry_point("noop")
            graph.set_finish_point("noop")
            return graph
        """
    )

    response = client.post(
        f"/api/workflows/{workflow.id}/versions/ingest",
        json={
            "script": script,
            "entrypoint": "build_graph",
            "metadata": {"language": "python"},
            "notes": "Initial LangGraph import",
            "created_by": "tester",
        },
    )

    assert response.status_code == 201
    version = response.json()
    assert version["metadata"] == {"language": "python"}
    assert version["notes"] == "Initial LangGraph import"
    assert version["graph"]["format"] == LANGGRAPH_SCRIPT_FORMAT
    assert "summary" in version["graph"]


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


def test_execution_history_not_found_returns_404() -> None:
    """Missing history records return a 404 response."""

    repository = InMemoryWorkflowRepository()
    history_store = InMemoryRunHistoryStore()
    app = create_app(repository, history_store=history_store)
    client = TestClient(app)

    response = client.get("/api/executions/missing/history")
    assert response.status_code == 404
    assert response.json()["detail"] == "Execution history not found"


def test_replay_execution_not_found_returns_404() -> None:
    """Replay API mirrors 404 behaviour for unknown executions."""

    repository = InMemoryWorkflowRepository()
    history_store = InMemoryRunHistoryStore()
    app = create_app(repository, history_store=history_store)
    client = TestClient(app)

    response = client.post("/api/executions/missing/replay", json={"from_step": 0})
    assert response.status_code == 404
    assert response.json()["detail"] == "Execution history not found"


def test_ingest_workflow_version_invalid_script_returns_400() -> None:
    """Invalid LangGraph scripts return a 400 error."""

    repository = InMemoryWorkflowRepository()
    workflow = asyncio.run(
        repository.create_workflow(
            name="Bad Script", slug=None, description=None, tags=[], actor="tester"
        )
    )

    app = create_app(repository)
    client = TestClient(app)

    invalid_script = "this is not valid python code!!!"

    response = client.post(
        f"/api/workflows/{workflow.id}/versions/ingest",
        json={
            "script": invalid_script,
            "entrypoint": "build_graph",
            "created_by": "tester",
        },
    )

    assert response.status_code == 400
    assert "detail" in response.json()


def test_ingest_workflow_version_missing_workflow_returns_404() -> None:
    """Ingesting a script for a non-existent workflow returns 404."""

    repository = InMemoryWorkflowRepository()
    app = create_app(repository)
    client = TestClient(app)

    from uuid import uuid4

    missing_id = str(uuid4())

    script = textwrap.dedent(
        """
        from langgraph.graph import StateGraph
        from orcheo.graph.state import State

        def build_graph():
            graph = StateGraph(State)
            graph.add_node("noop", lambda state: state)
            graph.set_entry_point("noop")
            graph.set_finish_point("noop")
            return graph
        """
    )

    response = client.post(
        f"/api/workflows/{missing_id}/versions/ingest",
        json={
            "script": script,
            "entrypoint": "build_graph",
            "created_by": "tester",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workflow not found"


@pytest.mark.asyncio
async def test_ingest_workflow_version_raises_not_found_error() -> None:
    """Repository lookups raising ``WorkflowNotFoundError`` propagate as 404s."""

    script = textwrap.dedent(
        """
        from langgraph.graph import StateGraph
        from orcheo.graph.state import State

        def build_graph():
            graph = StateGraph(State)
            graph.add_node("noop", lambda state: state)
            graph.set_entry_point("noop")
            graph.set_finish_point("noop")
            return graph
        """
    )

    request = WorkflowVersionIngestRequest(
        script=script,
        entrypoint="build_graph",
        created_by="tester",
    )

    class FailingRepository(InMemoryWorkflowRepository):
        async def create_version(
            self,
            workflow_id: UUID,
            *,
            graph: dict[str, object],
            metadata: dict[str, object],
            notes: str | None,
            created_by: str,
        ):
            raise WorkflowNotFoundError(str(workflow_id))

    repository = FailingRepository()

    with pytest.raises(HTTPException) as exc_info:
        await ingest_workflow_version(uuid4(), request, repository)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "Workflow not found"
