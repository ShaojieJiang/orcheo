"""Trigger coverage tests ensuring credential health errors bubble up."""

from __future__ import annotations
import importlib
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from orcheo.vault.oauth import CredentialHealthError, CredentialHealthReport


backend_app = importlib.import_module("orcheo_backend.app")


def _health_error() -> CredentialHealthError:
    """Construct a reusable CredentialHealthError."""
    report = CredentialHealthReport(
        workflow_id=uuid4(),
        results=[],
        checked_at=datetime.now(tz=UTC),
    )
    return CredentialHealthError(report)


def test_webhook_trigger_credential_health_error(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Webhook trigger returns 422 when credential health fails."""
    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Webhook Flow", "actor": "tester"},
    )
    workflow_id = workflow_response.json()["id"]

    api_client.post(
        f"/api/workflows/{workflow_id}/versions",
        json={"graph": {}, "metadata": {}, "created_by": "tester"},
    )

    repository = api_client.app.dependency_overrides[backend_app.get_repository]()

    async def failing_webhook_handler(*args: Any, **kwargs: Any) -> None:
        raise _health_error()

    monkeypatch.setattr(repository, "handle_webhook_trigger", failing_webhook_handler)

    response = api_client.post(f"/api/workflows/{workflow_id}/triggers/webhook")
    assert response.status_code == 422


def test_dispatch_cron_credential_health_error(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cron dispatch surfaces credential health errors."""
    repository = api_client.app.dependency_overrides[backend_app.get_repository]()

    async def failing_cron_dispatch(*args: Any, **kwargs: Any) -> None:
        raise _health_error()

    monkeypatch.setattr(repository, "dispatch_due_cron_runs", failing_cron_dispatch)

    response = api_client.post("/api/triggers/cron/dispatch")
    assert response.status_code == 422


def test_dispatch_manual_credential_health_error(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Manual dispatch surfaces credential health errors."""
    workflow_response = api_client.post(
        "/api/workflows",
        json={"name": "Manual Flow", "actor": "tester"},
    )
    workflow_id = workflow_response.json()["id"]

    repository = api_client.app.dependency_overrides[backend_app.get_repository]()

    async def failing_manual_dispatch(*args: Any, **kwargs: Any) -> None:
        raise _health_error()

    monkeypatch.setattr(repository, "dispatch_manual_runs", failing_manual_dispatch)

    response = api_client.post(
        "/api/triggers/manual/dispatch",
        json={
            "workflow_id": workflow_id,
            "actor": "tester",
            "runs": [{}],
        },
    )
    assert response.status_code == 422
