"""Tests for execution history REST endpoints exposed by the FastAPI app."""

import asyncio
from fastapi.testclient import TestClient
from orcheo_backend.app import create_app
from orcheo_backend.app.history import InMemoryRunHistoryStore
from orcheo_backend.app.repository import InMemoryWorkflowRepository


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
