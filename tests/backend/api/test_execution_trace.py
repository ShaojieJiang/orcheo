from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from orcheo_backend.app.dependencies import get_history_store, set_history_store
from orcheo_backend.app.history import InMemoryRunHistoryStore


async def _seed_trace_data(store: InMemoryRunHistoryStore) -> None:
    started_at = datetime.now(tz=UTC)
    await store.start_run(
        workflow_id="wf-trace",
        execution_id="exec-trace",
        inputs={"question": "hi"},
        trace_id="trace-abc",
        trace_started_at=started_at,
    )
    await store.append_step(
        "exec-trace",
        {
            "node-1": {
                "id": "node-1",
                "display_name": "Draft",
                "status": "success",
                "token_usage": {"input": 5, "output": 2},
                "artifacts": [{"id": "artifact-1"}],
            }
        },
    )
    await store.append_step(
        "exec-trace",
        {
            "node-2": {
                "id": "node-2",
                "display_name": "Refine",
                "status": "success",
                "token_usage": {"input": 7, "output": 5},
            }
        },
    )
    await store.mark_completed("exec-trace")


def test_get_execution_trace(api_client: TestClient) -> None:
    """The trace endpoint should return serialized spans."""

    store = InMemoryRunHistoryStore()
    set_history_store(store)
    api_client.app.dependency_overrides[get_history_store] = lambda: store
    asyncio.run(_seed_trace_data(store))

    response = api_client.get("/api/executions/exec-trace/trace")
    assert response.status_code == 200

    payload = response.json()
    assert payload["execution"]["id"] == "exec-trace"
    assert payload["execution"]["trace_id"] == "trace-abc"
    spans = payload["spans"]
    assert len(spans) >= 3
    root_span = spans[0]
    assert root_span["parent_span_id"] is None
    child_names = {span["name"] for span in spans[1:]}
    assert "Draft" in child_names
    assert "Refine" in child_names
    token_usage = payload["execution"].get("token_usage")
    assert token_usage == {"input": 12, "output": 7}
    assert payload["page_info"]["has_next_page"] is False
