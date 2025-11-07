"""Tests for HTTP executor retry, transport, and error recovery behavior."""

from __future__ import annotations
import httpx
import pytest
from orcheo_sdk import (
    HttpWorkflowExecutor,
    OrcheoClient,
    WorkflowExecutionError,
)


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
