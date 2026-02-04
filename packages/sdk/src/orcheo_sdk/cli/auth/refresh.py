"""OAuth token refresh implementation."""

from __future__ import annotations
import time
import httpx
from orcheo_sdk.cli.auth.config import get_oauth_config, is_oauth_configured
from orcheo_sdk.cli.auth.tokens import (
    AuthTokens,
    get_oauth_tokens,
    is_oauth_token_valid,
    set_oauth_tokens,
)


def _load_discovery_token_endpoint(issuer: str) -> str | None:
    """Fetch only the token endpoint from discovery.

    Returns None when discovery JSON is invalid or missing the token endpoint.
    """
    url = f"{issuer}/.well-known/openid-configuration"
    response = httpx.get(url, timeout=30.0)
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None

    token_endpoint = payload.get("token_endpoint")
    if not isinstance(token_endpoint, str):
        return None

    return token_endpoint


def refresh_oauth_tokens(*, profile: str | None) -> AuthTokens | None:
    """Attempt to refresh OAuth tokens using refresh_token.

    Returns refreshed tokens if successful, None if refresh not possible.
    """
    if not is_oauth_configured(profile=profile):
        return None

    tokens = get_oauth_tokens(profile=profile)
    if not tokens or not tokens.refresh_token:
        return None

    try:
        config = get_oauth_config(profile=profile)
        token_endpoint = _load_discovery_token_endpoint(config.issuer)
        if not token_endpoint:
            return None

        response = httpx.post(
            token_endpoint,
            data={
                "grant_type": "refresh_token",
                "client_id": config.client_id,
                "refresh_token": tokens.refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError:
        return None

    access_token = data.get("access_token")
    if not access_token:
        return None

    # Calculate expiry
    expires_at: int | None
    expires_in = data.get("expires_in")
    if isinstance(expires_in, int | float):
        expires_at = int((time.time() + expires_in) * 1000)
    else:
        expires_at = tokens.expires_at

    new_tokens = AuthTokens(
        access_token=access_token,
        id_token=data.get("id_token", tokens.id_token),
        refresh_token=data.get("refresh_token", tokens.refresh_token),
        token_type=data.get("token_type", tokens.token_type),
        expires_at=expires_at,
    )

    set_oauth_tokens(profile=profile, tokens=new_tokens)
    return new_tokens


def get_valid_access_token(*, profile: str | None) -> str | None:
    """Get a valid access token, refreshing if needed.

    Priority:
    1. Return existing valid OAuth token
    2. Attempt refresh if token expired but refresh_token exists
    3. Return None if no valid token available
    """
    tokens = get_oauth_tokens(profile=profile)

    if tokens and is_oauth_token_valid(tokens):
        return tokens.access_token

    # Token expired or missing, try refresh
    refreshed = refresh_oauth_tokens(profile=profile)
    if refreshed:
        return refreshed.access_token

    return None
