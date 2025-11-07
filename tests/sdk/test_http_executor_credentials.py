from __future__ import annotations
from collections.abc import Mapping
from types import TracebackType
from typing import Any
import httpx
import pytest
from orcheo_sdk import HttpWorkflowExecutor, OrcheoClient


def test_http_executor_fetches_credential_health() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"status": "healthy"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://localhost")
    executor = HttpWorkflowExecutor(
        client=OrcheoClient(base_url="http://localhost"),
        http_client=http_client,
    )

    try:
        payload = executor.get_credential_health("workflow")
    finally:
        http_client.close()

    assert payload == {"status": "healthy"}
    assert calls[0].method == "GET"


def test_http_executor_validates_credentials() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, base_url="http://localhost")
    executor = HttpWorkflowExecutor(
        client=OrcheoClient(base_url="http://localhost"),
        http_client=http_client,
    )

    try:
        payload = executor.validate_credentials("workflow", actor="qa")
    finally:
        http_client.close()

    assert payload == {"status": "ok"}
    assert calls[0].method == "POST"
    assert b"qa" in calls[0].content


def test_relative_url_passthrough_when_base_mismatch() -> None:
    result = HttpWorkflowExecutor._relative_url(
        "http://example.com/callback", "http://localhost"
    )
    assert result == "http://example.com/callback"


def test_relative_url_returns_root_when_equal_base() -> None:
    result = HttpWorkflowExecutor._relative_url("http://localhost", "http://localhost")
    assert result == "/"


def test_should_retry_matches_retry_statuses(client: OrcheoClient) -> None:
    executor = HttpWorkflowExecutor(client=client)
    assert executor._should_retry(500)
    assert not executor._should_retry(418)


def test_http_executor_internal_get_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

        def get(self, url: str, headers: Mapping[str, str]) -> httpx.Response:
            captured["url"] = url
            captured["headers"] = dict(headers)
            request = httpx.Request("GET", url, headers=headers)
            return httpx.Response(200, json={"status": "ok"}, request=request)

    monkeypatch.setattr("orcheo_sdk.client.httpx.Client", DummyClient)

    executor = HttpWorkflowExecutor(
        client=OrcheoClient(base_url="http://localhost"),
        max_retries=0,
        backoff_factor=0.0,
        transport=object(),
    )

    payload = executor.get_credential_health("workflow")

    assert payload == {"status": "ok"}
    assert captured["kwargs"]["base_url"] == "http://localhost"
    assert "transport" in captured["kwargs"]
    assert captured["url"] == "/api/workflows/workflow/credentials/health"


def test_http_executor_internal_get_client_without_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

        def get(self, url: str, headers: Mapping[str, str]) -> httpx.Response:
            captured["url"] = url
            request = httpx.Request("GET", url, headers=headers)
            return httpx.Response(200, json={"status": "ok"}, request=request)

    monkeypatch.setattr("orcheo_sdk.client.httpx.Client", DummyClient)

    executor = HttpWorkflowExecutor(
        client=OrcheoClient(base_url="http://localhost"),
        max_retries=0,
        backoff_factor=0.0,
    )

    payload = executor.get_credential_health("workflow")

    assert payload == {"status": "ok"}
    assert captured["kwargs"]["base_url"] == "http://localhost"
    assert "transport" not in captured["kwargs"]


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
