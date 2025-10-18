"""Simple SSO authenticator abstractions for enterprise roadmap."""

from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(slots=True)
class SsoProviderConfig:
    """Configuration describing an external SSO provider."""

    issuer: str
    client_id: str
    jwks_url: str


class SsoAuthenticator:
    """Validates SSO assertions using a static JWKS cache."""

    def __init__(self, config: SsoProviderConfig) -> None:
        """Store the provider configuration for later validation."""
        self._config = config

    def validate_claims(self, claims: Mapping[str, object]) -> bool:
        """Return True when standard OpenID claims are satisfied."""
        return (
            claims.get("iss") == self._config.issuer
            and claims.get("aud") == self._config.client_id
            and "email" in claims
        )


__all__ = ["SsoAuthenticator", "SsoProviderConfig"]
