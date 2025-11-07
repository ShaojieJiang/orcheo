"""Trigger layer webhook dispatch tests."""

from __future__ import annotations
from datetime import UTC, datetime
from uuid import UUID, uuid4
import pytest
from orcheo.models import CredentialHealthStatus
from orcheo.triggers import (
    RateLimitConfig,
    TriggerLayer,
    WebhookRequest,
    WebhookTriggerConfig,
    WebhookValidationError,
)
from orcheo.vault.oauth import (
    CredentialHealthError,
    CredentialHealthReport,
    CredentialHealthResult,
)


def test_webhook_dispatch_validation_and_normalization() -> None:
    """Webhook dispatch plans include normalized payload and metadata."""

    workflow_id = uuid4()
    layer = TriggerLayer()

    config = WebhookTriggerConfig(
        allowed_methods=["post"],
        required_headers={"X-Auth": "secret"},
        required_query_params={"team": "ops"},
        rate_limit=RateLimitConfig(limit=10, interval_seconds=60),
    )
    stored = layer.configure_webhook(workflow_id, config)
    assert stored.allowed_methods == ["POST"]

    request = WebhookRequest(
        method="POST",
        headers={"X-Auth": "secret"},
        query_params={"team": "ops"},
        payload={"key": "value"},
        source_ip="203.0.113.5",
    )

    dispatch = layer.prepare_webhook_dispatch(workflow_id, request)
    assert dispatch.triggered_by == "webhook"
    assert dispatch.actor == "webhook"
    assert dispatch.input_payload["headers"]["x-auth"] == "secret"
    assert dispatch.input_payload["query_params"] == {"team": "ops"}
    assert dispatch.input_payload["source_ip"] == "203.0.113.5"


def test_webhook_dispatch_redacts_shared_secret_header() -> None:
    """Shared secret headers are removed from dispatch payloads."""

    workflow_id = uuid4()
    layer = TriggerLayer()
    layer.configure_webhook(
        workflow_id,
        WebhookTriggerConfig(
            shared_secret_header="x-secret",
            shared_secret="expected",
        ),
    )
    request = WebhookRequest(
        method="POST",
        headers={"X-Secret": "expected", "X-Other": "value"},
        query_params={},
        payload={},
        source_ip=None,
    )

    dispatch = layer.prepare_webhook_dispatch(workflow_id, request)

    assert "x-secret" not in dispatch.input_payload["headers"]
    assert dispatch.input_payload["headers"]["x-other"] == "value"


def test_trigger_layer_blocks_unhealthy_workflows() -> None:
    workflow_id = uuid4()
    report = CredentialHealthReport(
        workflow_id=workflow_id,
        results=[
            CredentialHealthResult(
                credential_id=uuid4(),
                name="Slack",
                provider="slack",
                status=CredentialHealthStatus.UNHEALTHY,
                last_checked_at=datetime.now(tz=UTC),
                failure_reason="expired",
            )
        ],
        checked_at=datetime.now(tz=UTC),
    )

    class Guard:
        def is_workflow_healthy(self, workflow_id: UUID) -> bool:  # noqa: D401 - simple guard
            return False

        def get_report(self, workflow_id: UUID) -> CredentialHealthReport | None:
            return report if workflow_id == report.workflow_id else None

    layer = TriggerLayer(health_guard=Guard())
    layer.configure_webhook(
        workflow_id,
        WebhookTriggerConfig(allowed_methods=["post"]),
    )
    request = WebhookRequest(
        method="POST",
        headers={},
        query_params={},
        payload={},
        source_ip=None,
    )

    with pytest.raises(CredentialHealthError):
        layer.prepare_webhook_dispatch(workflow_id, request)


def test_trigger_layer_health_guard_can_be_replaced() -> None:
    workflow_id = uuid4()

    class Guard:
        def __init__(self) -> None:
            self.calls = 0

        def is_workflow_healthy(self, workflow_id: UUID) -> bool:
            self.calls += 1
            return True

        def get_report(self, workflow_id: UUID):  # pragma: no cover - unused
            return None

    guard = Guard()
    layer = TriggerLayer()
    layer.set_health_guard(guard)
    layer.configure_webhook(workflow_id, WebhookTriggerConfig(allowed_methods=["post"]))
    request = WebhookRequest(
        method="POST",
        headers={},
        query_params={},
        payload={},
        source_ip=None,
    )

    layer.prepare_webhook_dispatch(workflow_id, request)
    assert guard.calls == 1


def test_trigger_layer_allows_missing_health_report() -> None:
    workflow_id = uuid4()

    class Guard:
        def is_workflow_healthy(self, workflow_id: UUID) -> bool:
            return False

        def get_report(self, workflow_id: UUID):
            return None

    layer = TriggerLayer(health_guard=Guard())
    # Should not raise since the guard lacks a report explaining the failure.
    layer._ensure_healthy(workflow_id)


def test_malformed_configuration_handling() -> None:
    """Malformed configurations are handled gracefully."""

    layer = TriggerLayer()
    workflow_id = uuid4()

    layer.configure_webhook(
        workflow_id, WebhookTriggerConfig(required_headers={"X-Auth": "secret"})
    )

    invalid_request = WebhookRequest(
        method="POST",
        headers={},  # Missing required header
        query_params={},
        payload={"test": "data"},
    )

    with pytest.raises(WebhookValidationError):
        layer.prepare_webhook_dispatch(workflow_id, invalid_request)
