from __future__ import annotations
import hmac
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
import httpx
import jwt
from fastapi import status
from jwt import PyJWK, PyJWKError
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidTokenError,
)
from .context import RequestContext
from .errors import AuthenticationError
from .jwks import JWKSCache, JWKSFetcher
from .service_tokens import ServiceTokenManager
from .settings import AuthSettings
from .telemetry import AuthEvent, auth_telemetry
from .utils import coerce_str_items, parse_timestamp


if TYPE_CHECKING:
    from .service_tokens import ServiceTokenRecord


logger = logging.getLogger(__name__)


class Authenticator:
    """Validate bearer tokens against service tokens or JWT configuration."""

    def __init__(
        self, settings: AuthSettings, token_manager: ServiceTokenManager
    ) -> None:
        """Create the authenticator using resolved configuration."""
        self._settings = settings
        self._token_manager = token_manager
        self._jwks_cache: JWKSCache | None = None
        if settings.jwks_url:
            self._jwks_cache = JWKSCache(self._fetch_jwks, settings.jwks_cache_ttl)
        self._static_jwks: list[tuple[PyJWK, str | None]] = []
        for entry in settings.jwks_static:
            try:
                jwk = PyJWK.from_dict(dict(entry))
            except PyJWKError as exc:  # pragma: no cover - defensive
                logger.warning("Invalid JWKS entry skipped: %s", exc)
                continue
            algorithm_hint = entry.get("alg") if isinstance(entry, Mapping) else None
            algorithm_str = algorithm_hint if isinstance(algorithm_hint, str) else None
            self._static_jwks.append((jwk, algorithm_str))

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

        identity = await self._authenticate_service_token(token)
        if identity is not None:
            return identity

        if (
            self._settings.jwt_secret
            or self._settings.jwks_url
            or self._settings.jwks_static
        ):
            return await self._authenticate_jwt(token)

        raise AuthenticationError("Invalid bearer token", code="auth.invalid_token")

    async def _authenticate_service_token(self, token: str) -> RequestContext | None:
        """Return a RequestContext for a matching service or bootstrap token."""
        service_record = await self._try_authenticate_service_token(token)
        if service_record is not None:
            return self._service_record_to_context(service_record)

        bootstrap_token = self._settings.bootstrap_service_token
        if not (bootstrap_token and hmac.compare_digest(token, bootstrap_token)):
            return None

        expires_at = self._settings.bootstrap_token_expires_at
        if expires_at and datetime.now(tz=UTC) >= expires_at:
            logger.warning("Bootstrap service token has expired and will be rejected")
            auth_telemetry.record_auth_failure(
                reason="bootstrap_service_token_expired",
            )
            raise AuthenticationError(
                "Bootstrap service token has expired",
                code="auth.token_expired",
            )

        auth_telemetry.record(
            AuthEvent(
                event="authenticate",
                status="success",
                subject="bootstrap",
                identity_type="bootstrap_service",
                token_id="bootstrap",
                detail="Bootstrap service token used",
            )
        )
        claims = {
            "token_type": "bootstrap_service",
            "token_id": "bootstrap",
            "scopes": sorted(self._settings.bootstrap_token_scopes),
        }
        if expires_at:
            claims["expires_at"] = expires_at.isoformat()
        return RequestContext(
            subject="bootstrap",
            identity_type="service",
            scopes=self._settings.bootstrap_token_scopes,
            workspace_ids=frozenset(),
            token_id="bootstrap",
            issued_at=None,
            expires_at=expires_at,
            claims=claims,
        )

    async def _try_authenticate_service_token(
        self, token: str
    ) -> ServiceTokenRecord | None:
        """Attempt to match ``token`` against persisted service tokens."""
        if not await self._token_manager.all():
            return None
        try:
            return await self._token_manager.authenticate(token)
        except AuthenticationError as exc:
            if exc.code == "auth.invalid_token":
                return None
            raise

    @staticmethod
    def _service_record_to_context(record: ServiceTokenRecord) -> RequestContext:
        """Convert a service token record into a request context."""
        claims = {
            "token_type": "service",
            "token_id": record.identifier,
            "scopes": sorted(record.scopes),
            "workspace_ids": sorted(record.workspace_ids),
            "rotated_to": record.rotated_to,
            "revoked_at": record.revoked_at.isoformat() if record.revoked_at else None,
        }
        return RequestContext(
            subject=record.identifier,
            identity_type="service",
            scopes=record.scopes,
            workspace_ids=record.workspace_ids,
            token_id=record.identifier,
            issued_at=record.issued_at,
            expires_at=record.expires_at,
            claims=claims,
        )

    async def _authenticate_jwt(self, token: str) -> RequestContext:
        """Validate a JWT and return an authenticated context."""
        header = self._extract_header(token)
        key = await self._select_signing_key(header)
        claims = self._decode_claims(token, key)
        return self._claims_to_context(claims)

    def _extract_header(self, token: str) -> Mapping[str, Any]:
        """Return the unverified JWT header while enforcing allowed algorithms."""
        try:
            header = jwt.get_unverified_header(token)
        except InvalidTokenError as exc:  # pragma: no cover - defensive
            message = "Invalid bearer token"
            raise AuthenticationError(message, code="auth.invalid_token") from exc

        algorithm = header.get("alg")
        allowed = self._settings.allowed_algorithms
        if allowed and algorithm and algorithm not in allowed:
            message = "Bearer token is signed with an unsupported algorithm"
            raise AuthenticationError(message, code="auth.unsupported_algorithm")
        return header

    async def _select_signing_key(self, header: Mapping[str, Any]) -> Any:
        """Determine which signing key should be used for token validation."""
        algorithm = header.get("alg")
        if (
            self._settings.jwt_secret
            and isinstance(algorithm, str)
            and algorithm.startswith("HS")
        ):
            return self._settings.jwt_secret

        key = await self._resolve_signing_key(header)
        if key is None:
            message = "Unable to resolve signing key for bearer token"
            raise AuthenticationError(
                message,
                code="auth.key_unavailable",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return key

    def _decode_claims(self, token: str, key: Any) -> Mapping[str, Any]:
        """Decode JWT claims and map validation errors to AuthenticationError."""
        decode_args: dict[str, Any] = {
            "algorithms": self._settings.allowed_algorithms or None,
            "options": {"verify_aud": bool(self._settings.audiences)},
        }
        if self._settings.audiences:
            decode_args["audience"] = list(self._settings.audiences)
        if self._settings.issuer:
            decode_args["issuer"] = self._settings.issuer

        try:
            return jwt.decode(token, key, **decode_args)
        except ExpiredSignatureError as exc:
            raise AuthenticationError(
                "Bearer token has expired",
                code="auth.token_expired",
            ) from exc
        except InvalidAudienceError as exc:
            raise AuthenticationError(
                "Bearer token has an invalid audience",
                code="auth.invalid_audience",
                status_code=status.HTTP_403_FORBIDDEN,
            ) from exc
        except InvalidIssuerError as exc:
            raise AuthenticationError(
                "Bearer token has an invalid issuer",
                code="auth.invalid_issuer",
                status_code=status.HTTP_403_FORBIDDEN,
            ) from exc
        except InvalidTokenError as exc:
            raise AuthenticationError(
                "Invalid bearer token",
                code="auth.invalid_token",
            ) from exc

    async def _resolve_signing_key(self, header: Mapping[str, Any]) -> Any | None:
        """Return the signing key matching the provided token header."""
        kid = header.get("kid")
        algorithm = header.get("alg")
        key = self._match_static_key(kid, algorithm)
        if key is not None:
            return key

        if not self._jwks_cache:
            return None

        jwks = await self._jwks_cache.keys()
        return self._match_fetched_key(jwks, kid, algorithm)

    def _match_static_key(self, kid: Any, algorithm: Any) -> Any | None:
        """Return a key from the cached static JWKS entries when available."""
        for jwk, jwk_algorithm in self._static_jwks:
            if kid and jwk.key_id != kid:
                continue
            if algorithm and jwk_algorithm and jwk_algorithm != algorithm:
                continue
            return jwk.key
        return None

    def _match_fetched_key(
        self, entries: Sequence[Mapping[str, Any]], kid: Any, algorithm: Any
    ) -> Any | None:
        """Select a matching key from JWKS entries fetched at runtime."""
        for entry in entries:
            try:
                jwk = PyJWK.from_dict(dict(entry))
            except PyJWKError:  # pragma: no cover - invalid JWKS entries are skipped
                continue
            if kid and jwk.key_id != kid:
                continue
            entry_algorithm = entry.get("alg") if isinstance(entry, Mapping) else None
            algorithm_hint = (
                entry_algorithm if isinstance(entry_algorithm, str) else None
            )
            if algorithm and algorithm_hint and algorithm_hint != algorithm:
                continue
            return jwk.key
        return None

    async def _fetch_jwks(self) -> tuple[list[Mapping[str, Any]], int | None]:
        """Fetch JWKS data from the configured URL, returning keys and TTL."""
        if not self._settings.jwks_url:
            return [], None

        async with httpx.AsyncClient(timeout=self._settings.jwks_timeout) as client:
            response = await client.get(self._settings.jwks_url)
        response.raise_for_status()
        data = response.json()
        keys = data.get("keys", []) if isinstance(data, Mapping) else []
        ttl = _parse_max_age(response.headers.get("Cache-Control"))
        return [dict(item) for item in keys if isinstance(item, Mapping)], ttl

    def _claims_to_context(self, claims: Mapping[str, Any]) -> RequestContext:
        """Transform JWT claims into a request context."""
        subject = str(claims.get("sub") or "")
        identity_type = _infer_identity_type(claims)
        scopes = frozenset(_extract_scopes(claims))
        workspaces = frozenset(_extract_workspace_ids(claims))
        token_id_source = (
            claims.get("jti") or claims.get("token_id") or subject or identity_type
        )
        token_id = str(token_id_source)
        issued_at = parse_timestamp(claims.get("iat"))
        expires_at = parse_timestamp(claims.get("exp"))
        return RequestContext(
            subject=subject or token_id,
            identity_type=identity_type,
            scopes=scopes,
            workspace_ids=workspaces,
            token_id=token_id,
            issued_at=issued_at,
            expires_at=expires_at,
            claims=dict(claims),
        )


def _parse_max_age(cache_control: str | None) -> int | None:
    """Extract max-age from a Cache-Control header string."""
    if not cache_control:
        return None
    segments = [segment.strip() for segment in cache_control.split(",")]
    for segment in segments:
        if segment.lower().startswith("max-age"):
            try:
                _, value = segment.split("=", 1)
                return int(value.strip())
            except (ValueError, TypeError):  # pragma: no cover - defensive
                return None
    return None


def _infer_identity_type(claims: Mapping[str, Any]) -> str:
    """Determine the identity type from token claims."""
    for key in ("token_use", "type", "typ"):
        value = claims.get(key)
        if isinstance(value, str) and value:
            lowered = value.lower()
            if lowered in {"user", "service", "client"}:
                return "service" if lowered == "client" else lowered
    return "user"


def _extract_scopes(claims: Mapping[str, Any]) -> set[str]:
    """Normalize scope claim representations into a set of strings."""
    candidates: list[Any] = []
    for key in ("scope", "scopes", "scp"):
        value = claims.get(key)
        if value is not None:
            candidates.append(value)
    nested = claims.get("orcheo")
    if isinstance(nested, Mapping):
        nested_value = nested.get("scopes")
        if nested_value is not None:
            candidates.append(nested_value)

    scopes: set[str] = set()
    for candidate in candidates:
        scopes.update(coerce_str_items(candidate))
    return scopes


def _extract_workspace_ids(claims: Mapping[str, Any]) -> set[str]:
    """Collect workspace identifiers from common claim locations."""
    candidates: list[Any] = []
    for key in ("workspace_ids", "workspaces", "workspace", "workspace_id"):
        value = claims.get(key)
        if value is not None:
            candidates.append(value)
    nested = claims.get("orcheo")
    if isinstance(nested, Mapping):
        nested_value = nested.get("workspace_ids")
        if nested_value is not None:
            candidates.append(nested_value)

    workspaces: set[str] = set()
    for candidate in candidates:
        workspaces.update(coerce_str_items(candidate))
    return workspaces


__all__ = ["Authenticator", "JWKSFetcher"]
