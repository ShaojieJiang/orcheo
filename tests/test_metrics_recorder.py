"""Tests for runtime observability metrics."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from orcheo.models import CredentialHealthStatus, CredentialKind, OAuthTokenSecrets
from orcheo.observability.runtime import get_metrics_recorder
from orcheo.triggers.layer import TriggerLayer
from orcheo.vault import InMemoryCredentialVault
from orcheo.vault.oauth import (
    CredentialHealthReport,
    CredentialHealthResult,
    CredentialHealthStatus as HealthStatus,
    OAuthCredentialService,
    OAuthProvider,
    OAuthValidationResult,
)


class DummyProvider(OAuthProvider):
    async def refresh_tokens(self, metadata, tokens):  # type: ignore[override]
        return tokens

    async def validate_tokens(self, metadata, tokens):  # type: ignore[override]
        return OAuthValidationResult(status=HealthStatus.HEALTHY)


@pytest.mark.asyncio
async def test_credential_metrics_recorded() -> None:
    recorder = get_metrics_recorder()
    recorder.reset()

    vault = InMemoryCredentialVault()
    workflow_id = uuid4()
    vault.create_credential(
        name="OAuth",
        provider="openai",
        scopes=["ai:invoke"],
        secret="placeholder",
        actor="tester",
        kind=CredentialKind.OAUTH,
        oauth_tokens=OAuthTokenSecrets(access_token="abc"),
    )
    service = OAuthCredentialService(vault, token_ttl_seconds=60)
    service.register_provider("openai", DummyProvider())

    report = await service.ensure_workflow_health(workflow_id)
    assert report.is_healthy is True

    summary = recorder.summarize(str(workflow_id), "credential.health_latency")
    assert summary is not None and summary["count"] == 1
    failure_summary = recorder.summarize(str(workflow_id), "credential.health_failures")
    assert failure_summary is not None and failure_summary["max"] == 0


class UnhealthyGuard:
    def __init__(self, workflow_id: UUID) -> None:
        self.report = CredentialHealthReport(
            workflow_id=workflow_id,
            results=[
                CredentialHealthResult(
                    credential_id=workflow_id,
                    name="test",
                    provider="provider",
                    status=CredentialHealthStatus.UNHEALTHY,
                    last_checked_at=datetime.now(tz=UTC),
                    failure_reason="expired",
                )
            ],
            checked_at=datetime.now(tz=UTC),
        )

    def is_workflow_healthy(self, workflow_id: UUID) -> bool:
        return False

    def get_report(self, workflow_id: UUID) -> CredentialHealthReport | None:
        return self.report


@pytest.mark.asyncio
async def test_trigger_metrics_recorded() -> None:
    recorder = get_metrics_recorder()
    recorder.reset()
    workflow_id = uuid4()
    layer = TriggerLayer(health_guard=UnhealthyGuard(workflow_id))

    with pytest.raises(Exception):
        layer._ensure_healthy(workflow_id)

    summary = recorder.summarize(str(workflow_id), "trigger.blocked_runs")
    assert summary is not None and summary["max"] == 1
