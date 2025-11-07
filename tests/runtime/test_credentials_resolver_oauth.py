"""CredentialResolver tests for OAuth payload handling."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
import pytest
from orcheo.models import CredentialKind, CredentialScope, OAuthTokenSecrets
from orcheo.runtime.credentials import (
    CredentialResolver,
    UnknownCredentialPayloadError,
    credential_ref,
    credential_resolution,
)
from orcheo.vault import InMemoryCredentialVault


def test_resolver_supports_oauth_payload() -> None:
    vault = InMemoryCredentialVault()
    expires_at = datetime.now(tz=UTC) + timedelta(hours=1)
    vault.create_credential(
        name="oauth_bot",
        provider="oauth",
        scopes=["bot"],
        secret="ignored",
        actor="tester",
        kind=CredentialKind.OAUTH,
        scope=CredentialScope.unrestricted(),
        oauth_tokens=OAuthTokenSecrets(
            access_token="access", refresh_token="refresh", expires_at=expires_at
        ),
    )
    resolver = CredentialResolver(vault)
    with credential_resolution(resolver):
        tokens = resolver.resolve(credential_ref("oauth_bot", "oauth"))
        assert tokens.access_token == "access"
        assert (
            resolver.resolve(credential_ref("oauth_bot", "oauth.access_token"))
            == "access"
        )
        assert (
            resolver.resolve(credential_ref("oauth_bot", "oauth.expires_at"))
            == expires_at
        )


def test_resolver_returns_none_when_oauth_tokens_missing() -> None:
    vault = InMemoryCredentialVault()
    metadata = vault.create_credential(
        name="oauth_bot",
        provider="oauth",
        scopes=["bot"],
        secret="ignored",
        actor="tester",
        kind=CredentialKind.OAUTH,
        scope=CredentialScope.unrestricted(),
    )
    vault.update_oauth_tokens(credential_id=metadata.id, tokens=None, actor="tester")
    resolver = CredentialResolver(vault)
    with credential_resolution(resolver):
        assert resolver.resolve(credential_ref("oauth_bot", "oauth")) is None


def test_resolver_raises_for_missing_oauth_attribute() -> None:
    vault = InMemoryCredentialVault()
    vault.create_credential(
        name="oauth_bot",
        provider="oauth",
        scopes=["bot"],
        secret="ignored",
        actor="tester",
        kind=CredentialKind.OAUTH,
        scope=CredentialScope.unrestricted(),
        oauth_tokens=OAuthTokenSecrets(access_token="token"),
    )
    resolver = CredentialResolver(vault)
    with credential_resolution(resolver):
        with pytest.raises(UnknownCredentialPayloadError):
            resolver.resolve(credential_ref("oauth_bot", "oauth.invalid"))
