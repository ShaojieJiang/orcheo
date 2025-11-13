"""Tests for execution history REST endpoints exposed by the FastAPI app."""

import asyncio
from datetime import UTC, datetime
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


def test_execution_trace_endpoint_returns_spans() -> None:
    """Trace endpoint exposes span metadata derived from history."""

    repository = InMemoryWorkflowRepository()
    history_store = InMemoryRunHistoryStore()

    execution_id = "exec-trace"
    trace_id = "trace-xyz"
    started_at = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

    async def seed_history() -> None:
        await history_store.start_run(
            workflow_id="wf-trace",
            execution_id=execution_id,
            inputs={"topic": "observability"},
            trace_id=trace_id,
            trace_started_at=started_at,
        )
        await history_store.append_step(
            execution_id,
            {
                "llm": {
                    "id": "node-1",
                    "display_name": "Generate Summary",
                    "status": "completed",
                    "latency_ms": 1200,
                    "token_usage": {"input": 42, "output": 10},
                    "prompts": ["Summarise the incident log."],
                    "responses": ["Summary generated."],
                    "artifacts": [{"id": "artifact-1"}],
                }
            },
        )
        await history_store.append_step(execution_id, {"status": "completed"})
        await history_store.mark_completed(execution_id)

    asyncio.run(seed_history())

    app = create_app(repository, history_store=history_store)
    client = TestClient(app)

    response = client.get(f"/api/executions/{execution_id}/trace")
    assert response.status_code == 200
    payload = response.json()

    execution = payload["execution"]
    assert execution["execution_id"] == execution_id
    assert execution["trace_id"] == trace_id
    assert execution["token_usage"] == {"input": 42, "output": 10}

    spans = payload["spans"]
    assert len(spans) >= 2
    root_span = spans[0]
    child_span = spans[1]

    assert root_span["span_id"].endswith(":root")
    assert root_span["status"] == {"code": "OK", "message": None}
    assert child_span["parent_span_id"] == root_span["span_id"]
    assert child_span["attributes"]["orcheo.token.input"] == 42
    assert child_span["events"][0]["name"] == "prompt"


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
