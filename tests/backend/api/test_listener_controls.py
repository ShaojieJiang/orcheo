"""API tests for listener health, controls, and metrics."""

from __future__ import annotations
import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID
from fastapi.testclient import TestClient
from orcheo.listeners import ListenerHealthSnapshot, ListenerPlatform
from orcheo_backend.app.dependencies import (
    get_listener_runtime_store,
    get_repository,
)
from orcheo_backend.app.repository import InMemoryWorkflowRepository


async def _create_listener_workflow(
    repository: InMemoryWorkflowRepository,
) -> tuple[str, str]:
    workflow = await repository.create_workflow(
        name="Listener Flow",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )
    version = await repository.create_version(
        workflow.id,
        graph={
            "nodes": [],
            "edges": [],
            "index": {
                "listeners": [
                    {
                        "node_name": "telegram_listener",
                        "platform": "telegram",
                        "token": "[[telegram_token]]",
                        "allowed_updates": ["message"],
                        "allowed_chat_types": ["private"],
                    }
                ]
            },
        },
        metadata={},
        notes=None,
        created_by="tester",
    )
    return str(workflow.id), str(version.id)


def test_listener_endpoints_report_health_and_allow_pause_resume(
    api_client: TestClient,
) -> None:
    repository = get_repository()
    assert isinstance(repository, InMemoryWorkflowRepository)
    workflow_id, _version_id = asyncio.run(_create_listener_workflow(repository))
    subscription = asyncio.run(
        repository.list_listener_subscriptions(workflow_id=UUID(workflow_id))
    )[0]
    runtime_store = get_listener_runtime_store()
    runtime_store.clear()
    runtime_store.update(
        ListenerHealthSnapshot(
            subscription_id=subscription.id,
            runtime_id="listener-runtime-1",
            status="healthy",
            platform=ListenerPlatform.TELEGRAM,
            last_polled_at=datetime.now(tz=UTC),
            consecutive_failures=0,
        )
    )

    list_response = api_client.get(f"/api/workflows/{workflow_id}/listeners")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert len(payload) == 1
    assert payload[0]["runtime_status"] == "healthy"
    assert payload[0]["status"] == "active"

    pause_response = api_client.post(
        f"/api/workflows/{workflow_id}/listeners/{subscription.id}/pause",
        json={"actor": "tester"},
    )
    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"

    resume_response = api_client.post(
        f"/api/workflows/{workflow_id}/listeners/{subscription.id}/resume",
        json={"actor": "tester"},
    )
    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "active"


def test_listener_metrics_endpoint_surfaces_alerts(api_client: TestClient) -> None:
    repository = get_repository()
    assert isinstance(repository, InMemoryWorkflowRepository)
    workflow_id, _version_id = asyncio.run(_create_listener_workflow(repository))
    subscription = asyncio.run(
        repository.list_listener_subscriptions(workflow_id=UUID(workflow_id))
    )[0]
    runtime_store = get_listener_runtime_store()
    runtime_store.clear()
    runtime_store.update(
        ListenerHealthSnapshot(
            subscription_id=subscription.id,
            runtime_id="listener-runtime-1",
            status="backoff",
            platform=ListenerPlatform.TELEGRAM,
            last_polled_at=datetime.now(tz=UTC) - timedelta(minutes=10),
            consecutive_failures=4,
            detail="gateway reconnecting",
        )
    )
    repository._listener_subscriptions[subscription.id].last_error = "dispatch failed"  # type: ignore[attr-defined]

    response = api_client.get(
        f"/api/workflows/{workflow_id}/listeners/metrics?stall_threshold_seconds=60"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_subscriptions"] == 1
    assert payload["reconnecting_runtimes"] == 1
    kinds = {alert["kind"] for alert in payload["alerts"]}
    assert "reconnect_loop" in kinds
    assert "dispatch_failure" in kinds
