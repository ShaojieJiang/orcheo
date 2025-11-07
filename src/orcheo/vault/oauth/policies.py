"""Credential issuance and refresh policies."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from orcheo.models import CredentialIssuancePolicy, OAuthTokenSecrets


def validate_template_policy(
    policy: CredentialIssuancePolicy,
    *,
    oauth_tokens: OAuthTokenSecrets | None,
) -> None:
    """Ensure issued credentials satisfy template policy requirements."""
    if not policy.require_refresh_token:
        return
    if oauth_tokens is None or oauth_tokens.refresh_token is None:
        msg = "Template requires a refresh token for issued credentials."
        raise ValueError(msg)


def should_refresh_tokens(
    tokens: OAuthTokenSecrets | None,
    *,
    refresh_margin: timedelta,
) -> bool:
    """Return True if the provided tokens need to be refreshed."""
    if tokens is None:
        return True
    if tokens.expires_at is None:
        return False
    now = datetime.now(tz=UTC)
    return tokens.expires_at <= now + refresh_margin


__all__ = ["should_refresh_tokens", "validate_template_policy"]
