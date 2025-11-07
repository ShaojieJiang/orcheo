from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any
from .context import RequestContext
from .errors import AuthenticationError
from .jwks import JWKSCache, JWKSFetcher
from .jwt_authenticator import JWTAuthenticator
from .jwt_helpers import claims_to_context
from .service_token_authenticator import ServiceTokenAuthenticator
from .service_tokens import ServiceTokenManager
from .settings import AuthSettings


class Authenticator:
    """Validate bearer tokens using service tokens or JWT configuration."""

    def __init__(
        self, settings: AuthSettings, token_manager: ServiceTokenManager
    ) -> None:
        """Configure service token and JWT authenticators."""
        self._settings = settings
        self._token_manager = token_manager
        self._service_token_auth = ServiceTokenAuthenticator(settings, token_manager)
        self._jwt_authenticator = JWTAuthenticator(settings)

        async def _resolve_delegate(header: Mapping[str, Any]) -> Any | None:
            return await self._resolve_signing_key(header)

        self._jwt_authenticator._resolve_signing_key_func = _resolve_delegate

    @property
    def settings(self) -> AuthSettings:
        """Expose the resolved settings."""
        return self._settings

    @property
    def service_token_manager(self) -> ServiceTokenManager:
        """Expose the service token manager for lifecycle operations."""
        return self._token_manager

    async def authenticate(self, token: str) -> RequestContext:
        """Validate a bearer token and return the associated identity."""
        if not token:
            raise AuthenticationError("Missing bearer token", code="auth.missing_token")

        identity = await self._service_token_auth.authenticate(token)
        if identity is not None:
            return identity

        if self._jwt_authenticator.configured:
            return await self._jwt_authenticator.authenticate(token)

        raise AuthenticationError("Invalid bearer token", code="auth.invalid_token")

    @property
    def _jwks_cache(self) -> JWKSCache | None:
        """Expose the JWKS cache for compatibility with existing tests."""
        return self._jwt_authenticator.jwks_cache

    @_jwks_cache.setter
    def _jwks_cache(self, cache: JWKSCache | None) -> None:
        self._jwt_authenticator.jwks_cache = cache

    @property
    def _static_jwks(self) -> Sequence[tuple[Any, str | None]]:
        """Expose static JWKS entries for backwards compatibility."""
        return self._jwt_authenticator.static_jwks

    def _match_static_key(self, kid: Any, algorithm: Any) -> Any | None:
        """Delegate to the JWT authenticator for static key lookups."""
        return self._jwt_authenticator._match_static_key(kid, algorithm)

    def _match_fetched_key(
        self, entries: Sequence[Mapping[str, Any]], kid: Any, algorithm: Any
    ) -> Any | None:
        """Delegate to the JWT authenticator for dynamic JWKS selection."""
        return self._jwt_authenticator._match_fetched_key(entries, kid, algorithm)

    async def _resolve_signing_key(self, header: Mapping[str, Any]) -> Any | None:
        """Provide legacy access to the JWT signing key resolution logic."""
        return await self._jwt_authenticator._resolve_signing_key_impl(header)

    async def _fetch_jwks(self) -> tuple[list[Mapping[str, Any]], int | None]:
        """Invoke the underlying JWKS fetcher for compatibility."""
        return await self._jwt_authenticator._fetch_jwks()

    def _claims_to_context(self, claims: Mapping[str, Any]) -> RequestContext:
        """Preserve the historical helper used by downstream tests."""
        return claims_to_context(claims)


__all__ = ["Authenticator", "JWKSFetcher"]
