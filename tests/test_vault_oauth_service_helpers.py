"""Helper OAuth provider implementations for vault service tests."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from orcheo.models import CredentialHealthStatus, OAuthTokenSecrets
from orcheo.vault.oauth import OAuthProvider, OAuthValidationResult


class SuccessfulProvider(OAuthProvider):
    """Provider that refreshes tokens and reports healthy status."""

    def __init__(self) -> None:
        self.refresh_calls = 0
        self.validate_calls = 0

    async def refresh_tokens(self, metadata, tokens):  # type: ignore[override]
        self.refresh_calls += 1
        return OAuthTokenSecrets(
            access_token="refreshed-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(tz=UTC) + timedelta(hours=2),
        )

    async def validate_tokens(self, metadata, tokens):  # type: ignore[override]
        self.validate_calls += 1
        return OAuthValidationResult(status=CredentialHealthStatus.HEALTHY)


class FailingProvider(OAuthProvider):
    """Provider that always reports unhealthy credentials."""

    async def refresh_tokens(self, metadata, tokens):  # type: ignore[override]
        return tokens

    async def validate_tokens(self, metadata, tokens):  # type: ignore[override]
        return OAuthValidationResult(
            status=CredentialHealthStatus.UNHEALTHY,
            failure_reason="expired",
        )


class NoRefreshProvider(OAuthProvider):
    """Provider that cannot refresh tokens but validates health."""

    async def refresh_tokens(self, metadata, tokens):  # type: ignore[override]
        return None

    async def validate_tokens(self, metadata, tokens):  # type: ignore[override]
        return OAuthValidationResult(status=CredentialHealthStatus.HEALTHY)
