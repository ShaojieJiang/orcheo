"""Credential issuance policy and template tests split from the original suite."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialIssuancePolicy,
    CredentialKind,
    CredentialScope,
    CredentialTemplate,
    OAuthTokenSecrets,
)


def test_credential_issuance_policy_rotation_detection() -> None:
    policy = CredentialIssuancePolicy(rotation_period_days=7)
    now = datetime.now(tz=UTC)

    assert not policy.requires_rotation(last_rotated_at=now - timedelta(days=6))
    assert policy.requires_rotation(last_rotated_at=now - timedelta(days=8))
    assert not policy.requires_rotation(last_rotated_at=None)


def test_credential_template_instantiation_and_audit() -> None:
    cipher = AesGcmCredentialCipher(key="template-key")
    template = CredentialTemplate.create(
        name="Slack",
        provider="slack",
        scopes=["chat:write"],
        actor="alice",
        description="Slack bot",
        scope=CredentialScope.for_roles("admin"),
        kind=CredentialKind.OAUTH,
        issuance_policy=CredentialIssuancePolicy(
            require_refresh_token=True,
            rotation_period_days=30,
        ),
    )

    metadata = template.instantiate_metadata(
        name="Slack Prod",
        secret="client-secret",
        cipher=cipher,
        actor="alice",
        scopes=["chat:write", "chat:read"],
        oauth_tokens=OAuthTokenSecrets(access_token="tok", refresh_token="ref"),
    )

    assert metadata.template_id == template.id
    assert metadata.name == "Slack Prod"
    assert metadata.scopes == ["chat:write", "chat:read"]
    assert metadata.reveal(cipher=cipher) == "client-secret"
    template.record_issuance(actor="alice", credential_id=metadata.id)
    assert template.audit_log[-1].action == "credential_issued"
