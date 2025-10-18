"""Tests for automated security review helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4
import pytest
from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialKind,
    CredentialScope,
    OAuthTokenSecrets,
)
from orcheo.security import run_security_review
from orcheo.triggers.layer import TriggerLayer
from orcheo.triggers.webhook import WebhookTriggerConfig
from orcheo.vault import InMemoryCredentialVault
from orcheo.vault.oauth import OAuthCredentialService


@pytest.mark.asyncio()
async def test_security_review_reports_unhealthy_credentials() -> None:
    cipher = AesGcmCredentialCipher(key="review-key")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    context = CredentialAccessContext(workflow_id=workflow_id)
    metadata = vault.create_credential(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        secret="token",
        actor="alice",
        scope=CredentialScope.for_workflows(workflow_id),
        kind=CredentialKind.OAUTH,
        oauth_tokens=OAuthTokenSecrets(
            access_token="access",
            refresh_token=None,
            expires_at=datetime.now(tz=UTC),
        ),
    )
    vault.mark_health(
        credential_id=metadata.id,
        status=CredentialHealthStatus.UNHEALTHY,
        reason="expired",
        actor="monitor",
        context=context,
    )

    service = OAuthCredentialService(vault, token_ttl_seconds=600)
    triggers = TriggerLayer(health_guard=service)
    triggers.configure_webhook(workflow_id, WebhookTriggerConfig())

    review = run_security_review(
        workflow_id=workflow_id,
        vault=vault,
        triggers=triggers,
        health_guard=service,
    )

    assert not review.passed
    messages = {issue.message for issue in review.issues}
    assert any("missing refresh token" in msg for msg in messages)
    assert any("Credential" in msg for msg in messages)
    assert any("Webhook trigger" in issue.message for issue in review.issues)


@pytest.mark.asyncio()
async def test_security_review_passes_for_healthy_setup() -> None:
    cipher = AesGcmCredentialCipher(key="review-key-2")
    vault = InMemoryCredentialVault(cipher=cipher)
    workflow_id = uuid4()
    vault.create_credential(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        secret="token",
        actor="alice",
        scope=CredentialScope.for_workflows(workflow_id),
        kind=CredentialKind.OAUTH,
        oauth_tokens=OAuthTokenSecrets(
            access_token="access",
            refresh_token="refresh",
            expires_at=datetime.now(tz=UTC),
        ),
    )

    service = OAuthCredentialService(vault, token_ttl_seconds=600)
    triggers = TriggerLayer(health_guard=service)
    triggers.configure_webhook(
        workflow_id,
        WebhookTriggerConfig(
            shared_secret_header="x-signature",
            shared_secret="secret",
        ),
    )

    review = run_security_review(
        workflow_id=workflow_id,
        vault=vault,
        triggers=triggers,
        health_guard=service,
    )

    assert review.passed
    assert review.to_summary().startswith(f"Workflow {workflow_id}")
