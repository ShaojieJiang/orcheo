"""OAuth configuration resolution."""

from __future__ import annotations
import os
from dataclasses import dataclass
from orcheo_sdk.cli.errors import CLIConfigurationError


# Environment variable names matching Canvas conventions (without VITE_ prefix)
AUTH_ISSUER_ENV = "ORCHEO_AUTH_ISSUER"
AUTH_CLIENT_ID_ENV = "ORCHEO_AUTH_CLIENT_ID"
AUTH_SCOPES_ENV = "ORCHEO_AUTH_SCOPES"
AUTH_AUDIENCE_ENV = "ORCHEO_AUTH_AUDIENCE"
AUTH_ORGANIZATION_ENV = "ORCHEO_AUTH_ORGANIZATION"

DEFAULT_SCOPES = "openid profile email"


@dataclass(slots=True)
class OAuthConfig:
    """OAuth provider configuration."""

    issuer: str
    client_id: str
    scopes: str
    audience: str | None = None
    organization: str | None = None


def get_oauth_config() -> OAuthConfig:
    """Load OAuth configuration from environment variables.

    Raises:
        CLIConfigurationError: If required OAuth config is missing.
    """
    issuer = os.getenv(AUTH_ISSUER_ENV)
    client_id = os.getenv(AUTH_CLIENT_ID_ENV)

    if not issuer or not client_id:
        raise CLIConfigurationError(
            f"OAuth not configured. Set {AUTH_ISSUER_ENV} and {AUTH_CLIENT_ID_ENV}."
        )

    return OAuthConfig(
        issuer=issuer.rstrip("/"),
        client_id=client_id,
        scopes=os.getenv(AUTH_SCOPES_ENV, DEFAULT_SCOPES),
        audience=os.getenv(AUTH_AUDIENCE_ENV),
        organization=os.getenv(AUTH_ORGANIZATION_ENV),
    )


def is_oauth_configured() -> bool:
    """Check if OAuth environment variables are set."""
    return bool(os.getenv(AUTH_ISSUER_ENV) and os.getenv(AUTH_CLIENT_ID_ENV))
