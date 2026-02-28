from __future__ import annotations
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from orcheo_backend.app.repository.errors import (
    WorkflowVersionNotFoundError,
)
from .shared import create_workflow_with_version


def test_webhook_trigger_configuration_roundtrip(api_client: TestClient) -> None:
    """Validate webhook trigger configuration persistence."""

    workflow_id, _ = create_workflow_with_version(api_client)

    default_response = api_client.get(
        f"/api/workflows/{workflow_id}/triggers/webhook/config"
    )
    assert default_response.status_code == 200
    default_payload = default_response.json()
    assert set(default_payload["allowed_methods"]) == {"GET", "POST"}

    update_response = api_client.put(
        f"/api/workflows/{workflow_id}/triggers/webhook/config",
        json={
            "allowed_methods": ["POST", "GET"],
            "required_headers": {"x-custom": "value"},
            "required_query_params": {"env": "prod"},
            "shared_secret": "super-secret",
            "secret_header": "x-super-secret",
            "rate_limit": {"limit": 5, "interval_seconds": 60},
        },
    )
    assert update_response.status_code == 200
    updated_payload = update_response.json()
    assert set(updated_payload["allowed_methods"]) == {"POST", "GET"}
    assert updated_payload["required_headers"] == {"x-custom": "value"}
    assert updated_payload["required_query_params"] == {"env": "prod"}
    assert updated_payload["shared_secret"] == "super-secret"
    assert updated_payload["secret_header"] == "x-super-secret"

    roundtrip_response = api_client.get(
        f"/api/workflows/{workflow_id}/triggers/webhook/config"
    )
    assert roundtrip_response.status_code == 200
    assert roundtrip_response.json() == updated_payload


def test_webhook_trigger_execution_creates_run(api_client: TestClient) -> None:
    """Ensure webhook invocation creates a pending workflow run."""

    workflow_id, _ = create_workflow_with_version(api_client)

    api_client.put(
        f"/api/workflows/{workflow_id}/triggers/webhook/config",
        json={
            "allowed_methods": ["POST"],
            "required_headers": {"x-custom": "value"},
            "shared_secret": "token",
            "secret_header": "x-auth",
            "rate_limit": {"limit": 5, "interval_seconds": 60},
        },
    )

    trigger_response = api_client.post(
        f"/api/workflows/{workflow_id}/triggers/webhook",
        json={"message": "hello"},
        headers={
            "x-custom": "value",
            "x-auth": "token",
        },
        params={"extra": "context"},
    )
    assert trigger_response.status_code == 202
    run_payload = trigger_response.json()
    assert run_payload["triggered_by"] == "webhook"
    assert run_payload["status"] == "pending"

    runs_response = api_client.get(f"/api/workflows/{workflow_id}/runs")
    assert runs_response.status_code == 200
    runs = runs_response.json()
    assert len(runs) == 1
    stored_run = runs[0]
    assert stored_run["input_payload"]["body"] == {"message": "hello"}
    assert stored_run["input_payload"]["headers"]["x-custom"] == "value"
    assert stored_run["input_payload"]["query_params"] == {"extra": "context"}


def test_webhook_trigger_enforces_method_and_rate_limit(
    api_client: TestClient,
) -> None:
    """Ensure webhook trigger enforces method filters and rate limiting."""

    workflow_id, _ = create_workflow_with_version(api_client)

    api_client.put(
        f"/api/workflows/{workflow_id}/triggers/webhook/config",
        json={
            "allowed_methods": ["GET"],
            "rate_limit": {"limit": 1, "interval_seconds": 60},
        },
    )

    post_response = api_client.post(
        f"/api/workflows/{workflow_id}/triggers/webhook",
    )
    assert post_response.status_code == 405

    first_get = api_client.get(f"/api/workflows/{workflow_id}/triggers/webhook")
    assert first_get.status_code == 202

    second_get = api_client.get(f"/api/workflows/{workflow_id}/triggers/webhook")
    assert second_get.status_code == 429


def test_webhook_trigger_config_missing_workflow(api_client: TestClient) -> None:
    """Webhook config routes return 404 for unknown workflows."""

    missing = str(uuid4())
    response = api_client.put(
        f"/api/workflows/{missing}/triggers/webhook/config",
        json={"allowed_methods": ["POST"]},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Workflow not found"

    get_response = api_client.get(f"/api/workflows/{missing}/triggers/webhook/config")
    assert get_response.status_code == 404
    assert get_response.json()["detail"] == "Workflow not found"


def test_webhook_trigger_invoke_missing_workflow(api_client: TestClient) -> None:
    """Webhook invocation returns a not found error for unknown workflows."""

    missing = str(uuid4())
    response = api_client.post(f"/api/workflows/{missing}/triggers/webhook")
    assert response.status_code == 404
    assert response.json()["detail"] == "Workflow not found"


def test_webhook_trigger_invoke_requires_version(api_client: TestClient) -> None:
    """Webhook invocation requires at least one workflow version."""

    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "No Version Flow", "actor": "tester"},
    )
    workflow_id = workflow_response.json()["id"]

    with pytest.raises(WorkflowVersionNotFoundError):
        api_client.post(f"/api/workflows/{workflow_id}/triggers/webhook")


def test_webhook_trigger_accepts_non_json_body(api_client: TestClient) -> None:
    """Webhook invocation stores non-JSON payloads as raw bytes."""

    workflow_id, _ = create_workflow_with_version(api_client)

    api_client.put(
        f"/api/workflows/{workflow_id}/triggers/webhook/config",
        json={"allowed_methods": ["POST"]},
    )

    binary_payload = b"\xff\xfe"
    trigger_response = api_client.post(
        f"/api/workflows/{workflow_id}/triggers/webhook",
        content=binary_payload,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert trigger_response.status_code == 202

    runs_response = api_client.get(f"/api/workflows/{workflow_id}/runs")
    run_payload = runs_response.json()[0]["input_payload"]
    assert run_payload["body"] == {"raw": "��"}


def test_webhook_trigger_preserves_raw_body_when_requested(
    api_client: TestClient,
) -> None:
    """Webhook invocation can preserve the raw body alongside parsed JSON."""

    workflow_id, _ = create_workflow_with_version(api_client)

    api_client.put(
        f"/api/workflows/{workflow_id}/triggers/webhook/config",
        json={"allowed_methods": ["POST"]},
    )

    trigger_response = api_client.post(
        f"/api/workflows/{workflow_id}/triggers/webhook",
        json={"message": "hello"},
        params={"preserve_raw_body": "true"},
    )
    assert trigger_response.status_code == 202

    runs_response = api_client.get(f"/api/workflows/{workflow_id}/runs")
    run_payload = runs_response.json()[0]["input_payload"]["body"]
    assert run_payload["parsed"] == {"message": "hello"}
    assert isinstance(run_payload["raw"], str)
    assert "message" in run_payload["raw"]


def test_webhook_trigger_slack_url_verification_short_circuits(
    api_client: TestClient,
) -> None:
    """Slack url_verification requests respond with the challenge directly."""

    workflow_id, _ = create_workflow_with_version(api_client)

    response = api_client.post(
        f"/api/workflows/{workflow_id}/triggers/webhook",
        json={"type": "url_verification", "challenge": "abc123"},
    )
    assert response.status_code == 200
    assert response.json() == {"challenge": "abc123"}

    runs_response = api_client.get(f"/api/workflows/{workflow_id}/runs")
    assert runs_response.status_code == 200
    assert runs_response.json() == []


def test_webhook_trigger_accepts_handle_route(api_client: TestClient) -> None:
    """Webhook trigger config and invocation should accept a workflow handle."""
    response = api_client.post(
        "/api/workflows",
        json={
            "name": "Webhook Handle Flow",
            "handle": "webhook-handle-flow",
            "actor": "tester",
        },
    )
    assert response.status_code == 201
    workflow_id = response.json()["id"]

    api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={
            "graph": {"nodes": ["start"], "edges": []},
            "metadata": {},
            "created_by": "tester",
        },
    ).raise_for_status()

    config_response = api_client.put(
        "/api/workflows/webhook-handle-flow/triggers/webhook/config",
        json={"allowed_methods": ["POST"]},
    )
    assert config_response.status_code == 200

    trigger_response = api_client.post(
        "/api/workflows/webhook-handle-flow/triggers/webhook",
        json={"message": "hello"},
    )
    assert trigger_response.status_code == 202

    runs_response = api_client.get(f"/api/workflows/{workflow_id}/runs")
    assert runs_response.status_code == 200
    assert len(runs_response.json()) == 1
