"""Tests for the lightweight Orcheo Python SDK."""

from __future__ import annotations
from collections.abc import Mapping
from types import TracebackType
from typing import Any
import httpx
import pytest
from fastapi.testclient import TestClient
from orcheo_sdk import (
    HttpWorkflowExecutor,
    OrcheoClient,
    WorkflowExecutionError,
)
from orcheo_backend.app import create_app
from orcheo_backend.app.repository import InMemoryWorkflowRepository


@pytest.fixture
def client() -> OrcheoClient:
    return OrcheoClient(
        base_url="http://localhost:8000", default_headers={"X-Test": "1"}
    )


def test_workflow_trigger_url(client: OrcheoClient) -> None:
    assert (
        client.workflow_trigger_url("demo")
        == "http://localhost:8000/api/workflows/demo/runs"
    )


def test_workflow_trigger_url_requires_identifier(client: OrcheoClient) -> None:
    with pytest.raises(ValueError):
        client.workflow_trigger_url("   ")


def test_websocket_url_from_http(client: OrcheoClient) -> None:
    assert client.websocket_url("abc") == "ws://localhost:8000/ws/workflow/abc"


def test_websocket_url_from_https() -> None:
    client = OrcheoClient(base_url="https://example.com")
    assert client.websocket_url("wf") == "wss://example.com/ws/workflow/wf"


def test_websocket_url_requires_identifier(client: OrcheoClient) -> None:
    with pytest.raises(ValueError):
        client.websocket_url("   ")


def test_websocket_url_from_no_protocol() -> None:
    client = OrcheoClient(base_url="example.com")
    assert client.websocket_url("wf") == "ws://example.com/ws/workflow/wf"


def test_prepare_headers_merges_defaults(client: OrcheoClient) -> None:
    merged = client.prepare_headers({"Authorization": "Bearer token"})
    assert merged == {"X-Test": "1", "Authorization": "Bearer token"}


def test_prepare_headers_without_overrides(client: OrcheoClient) -> None:
    merged = client.prepare_headers()
    assert merged == {"X-Test": "1"}


def test_build_payload_supports_optional_execution_id(client: OrcheoClient) -> None:
    payload = client.build_payload({"nodes": []}, {"foo": "bar"}, execution_id="123")
    assert payload["execution_id"] == "123"
    assert payload["graph_config"] == {"nodes": []}
    assert payload["inputs"] == {"foo": "bar"}


def test_build_payload_without_execution_id(client: OrcheoClient) -> None:
    payload = client.build_payload({"nodes": []}, {"foo": "bar"})
    assert "execution_id" not in payload


def test_build_payload_returns_run_workflow_shape(client: OrcheoClient) -> None:
    graph_config = {"nodes": [{"name": "first"}], "edges": []}
    inputs = {"name": "Ada"}

    payload = client.build_payload(graph_config, inputs)

    assert payload["type"] == "run_workflow"
    assert payload["graph_config"] == graph_config
    assert payload["inputs"] == inputs
    # Ensure the payload does not share references with the provided mappings.
    graph_config["nodes"].append({"name": "mutated"})
    inputs["name"] = "Grace"
    assert payload["graph_config"]["nodes"] == [{"name": "first"}]
    assert payload["inputs"] == {"name": "Ada"}


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


def test_http_executor_retries_and_sets_auth_header() -> None:
    captured_delays: list[float] = []

    def capture_delay(delay: float) -> None:
        captured_delays.append(delay)

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(500)
        return httpx.Response(
            201,
            json={
                "id": "run-123",
                "status": "pending",
                "triggered_by": "tester",
                "input_payload": {"foo": "bar"},
            },
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://localhost")
    executor = HttpWorkflowExecutor(
        client=OrcheoClient(base_url="http://localhost"),
        http_client=http_client,
        auth_token="secret",
        max_retries=2,
        backoff_factor=0.2,
        sleep=capture_delay,
    )

    try:
        payload = executor.trigger_run(
            "workflow",
            workflow_version_id="version",
            triggered_by="tester",
            inputs={"foo": "bar"},
        )
    finally:
        http_client.close()

    assert len(calls) == 2
    assert calls[0].headers.get("Authorization") == "Bearer secret"
    assert payload["status"] == "pending"
    assert captured_delays == [0.2]


def test_http_executor_raises_after_exhausting_retries() -> None:
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://localhost")
    executor = HttpWorkflowExecutor(
        client=OrcheoClient(base_url="http://localhost"),
        http_client=http_client,
        max_retries=1,
        backoff_factor=0.0,
        sleep=lambda _delay: None,
    )

    try:
        with pytest.raises(WorkflowExecutionError) as exc_info:
            executor.trigger_run(
                "workflow",
                workflow_version_id="version",
                triggered_by="tester",
            )
    finally:
        http_client.close()

    assert attempts == 2
    assert exc_info.value.status_code == 503


def test_http_executor_recovers_from_transport_error() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(
            201,
            json={
                "id": "run-456",
                "status": "pending",
                "triggered_by": "tester",
                "input_payload": {},
            },
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://localhost")
    executor = HttpWorkflowExecutor(
        client=OrcheoClient(base_url="http://localhost"),
        http_client=http_client,
        max_retries=1,
        backoff_factor=0.0,
    )

    try:
        payload = executor.trigger_run(
            "workflow",
            workflow_version_id="version",
            triggered_by="tester",
        )
    finally:
        http_client.close()

    assert attempts == 2
    assert payload["status"] == "pending"


def test_http_executor_raises_on_persistent_transport_error() -> None:
    transport = httpx.MockTransport(
        lambda request: (_ for _ in ()).throw(
            httpx.ConnectError("boom", request=request)
        )
    )
    http_client = httpx.Client(transport=transport, base_url="http://localhost")
    executor = HttpWorkflowExecutor(
        client=OrcheoClient(base_url="http://localhost"),
        http_client=http_client,
        max_retries=0,
        backoff_factor=0.0,
    )

    try:
        with pytest.raises(WorkflowExecutionError) as exc_info:
            executor.trigger_run(
                "workflow",
                workflow_version_id="version",
                triggered_by="tester",
            )
    finally:
        http_client.close()

    assert exc_info.value.status_code is None


def test_http_executor_uses_internal_client_when_transport_provided() -> None:
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return httpx.Response(
            201,
            json={
                "id": "run-789",
                "status": "pending",
                "triggered_by": "tester",
                "input_payload": {},
            },
        )

    transport = httpx.MockTransport(handler)
    executor = HttpWorkflowExecutor(
        client=OrcheoClient(base_url="http://localhost"),
        transport=transport,
        max_retries=0,
        backoff_factor=0.0,
    )

    payload = executor.trigger_run(
        "workflow",
        workflow_version_id="version",
        triggered_by="tester",
    )

    assert payload["status"] == "pending"
    assert captured_urls == ["http://localhost/api/workflows/workflow/runs"]


def test_relative_url_passthrough_when_base_mismatch() -> None:
    result = HttpWorkflowExecutor._relative_url(
        "http://example.com/callback", "http://localhost"
    )
    assert result == "http://example.com/callback"


def test_http_executor_builds_default_client(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class DummyClient:
        def __init__(self, **kwargs: Any) -> None:
            captured["kwargs"] = kwargs

        def __enter__(self) -> DummyClient:
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> None:
            return None

        def post(
            self, url: str, json: Any, headers: Mapping[str, str]
        ) -> httpx.Response:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = dict(headers)
            return httpx.Response(
                201,
                json={
                    "id": "run-999",
                    "status": "pending",
                    "triggered_by": json["triggered_by"],
                    "input_payload": json["input_payload"],
                },
                request=httpx.Request("POST", url, headers=headers),
            )

    monkeypatch.setattr("orcheo_sdk.client.httpx.Client", DummyClient)

    executor = HttpWorkflowExecutor(
        client=OrcheoClient(base_url="http://localhost"),
        max_retries=0,
        backoff_factor=0.0,
    )

    payload = executor.trigger_run(
        "workflow",
        workflow_version_id="version",
        triggered_by="tester",
        inputs={"foo": "bar"},
    )

    assert payload["status"] == "pending"
    assert captured["kwargs"]["base_url"] == "http://localhost"
    assert captured["kwargs"]["timeout"] == executor.timeout
    assert captured["url"] == "/api/workflows/workflow/runs"
    assert captured["json"]["input_payload"] == {"foo": "bar"}


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
