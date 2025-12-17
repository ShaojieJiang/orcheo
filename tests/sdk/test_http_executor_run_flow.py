"""Integration-style tests for triggering workflow runs via the HTTP executor."""

from __future__ import annotations
import httpx
from fastapi.testclient import TestClient
from orcheo_backend.app import create_app
from orcheo_backend.app.repository import InMemoryWorkflowRepository
from orcheo_sdk import HttpWorkflowExecutor, OrcheoClient


def test_http_executor_triggers_run_against_backend() -> None:
    repository = InMemoryWorkflowRepository()
    app = create_app(repository)

    with TestClient(app) as api_client:
        transport = httpx.MockTransport(
            lambda request: _dispatch_to_app(api_client, request)
        )
        http_client = httpx.Client(transport=transport, base_url="http://testserver")
        sdk_client = OrcheoClient(base_url="http://testserver")
        executor = HttpWorkflowExecutor(
            client=sdk_client,
            http_client=http_client,
            auth_token="token-123",
            max_retries=0,
        )

        try:
            workflow_id, version_id = _create_workflow_and_version(http_client)
            payload = executor.trigger_run(
                workflow_id,
                workflow_version_id=version_id,
                triggered_by="runner",
                inputs={"value": 1},
            )
        finally:
            http_client.close()

    assert payload["status"] == "pending"
    assert payload["triggered_by"] == "runner"
    assert payload["input_payload"] == {"value": 1}


def _create_workflow_and_version(http_client: httpx.Client) -> tuple[str, str]:
    create_workflow = http_client.post(
        "/api/workflows",
        json={"name": "SDK Flow", "actor": "sdk"},
    )
    create_workflow.raise_for_status()
    workflow_id = create_workflow.json()["id"]

    create_version = http_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {"nodes": ["start"], "edges": []},
            "metadata": {},
            "created_by": "sdk",
        },
    )
    create_version.raise_for_status()
    version_id = create_version.json()["id"]

    return workflow_id, version_id


def _dispatch_to_app(api_client: TestClient, request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if request.url.query:
        path = f"{path}?{request.url.query}"

    response = api_client.request(
        request.method,
        path,
        headers={
            key: value
            for key, value in request.headers.items()
            if key.lower() != "host"
        },
        content=request.content,
    )

    return httpx.Response(
        status_code=response.status_code,
        headers=response.headers,
        content=response.content,
    )
