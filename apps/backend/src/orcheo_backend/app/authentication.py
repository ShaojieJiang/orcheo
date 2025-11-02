from __future__ import annotations
import asyncio
import hashlib
import hmac
import json
import logging
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
import httpx
import jwt
from fastapi import HTTPException, Request, WebSocket, status
from jwt import PyJWK, PyJWKError
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidTokenError,
)
from orcheo.config import get_settings


logger = logging.getLogger(__name__)


JWKSFetcher = Callable[[], Awaitable[tuple[list[Mapping[str, Any]], int | None]]]


@dataclass(frozen=True)
class RequestContext:
    """Authenticated identity attached to a request or WebSocket."""

    subject: str
    identity_type: str
    scopes: frozenset[str] = field(default_factory=frozenset)
    workspace_ids: frozenset[str] = field(default_factory=frozenset)
    token_id: str | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    claims: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        """Return True when the context represents an authenticated identity."""
        return self.identity_type != "anonymous"

    def has_scope(self, scope: str) -> bool:
        """Return True when the identity possesses the given scope."""
        return scope in self.scopes

    @classmethod
    def anonymous(cls) -> RequestContext:
        """Return a sentinel context representing unauthenticated access."""
        return cls(subject="anonymous", identity_type="anonymous")


@dataclass(frozen=True)
class ServiceTokenRecord:
    """Configuration describing a hashed service token."""

    identifier: str
    secret_hash: str
    scopes: frozenset[str] = field(default_factory=frozenset)
    workspace_ids: frozenset[str] = field(default_factory=frozenset)

    def matches(self, token: str) -> bool:
        """Return True when the provided token matches the stored hash."""
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return hmac.compare_digest(self.secret_hash, digest)


@dataclass(frozen=True)
class AuthSettings:
    """Resolved authentication configuration for the backend."""

    mode: str
    jwt_secret: str | None
    jwks_url: str | None
    jwks_static: tuple[Mapping[str, Any], ...]
    jwks_cache_ttl: int
    jwks_timeout: float
    allowed_algorithms: tuple[str, ...]
    audiences: tuple[str, ...]
    issuer: str | None
    service_tokens: tuple[ServiceTokenRecord, ...]

    @property
    def enforce(self) -> bool:
        """Return True when authentication should be enforced for requests."""
        if self.mode == "disabled":
            return False
        if self.mode == "required":
            return True
        return bool(
            self.jwt_secret or self.jwks_url or self.jwks_static or self.service_tokens
        )


@dataclass(eq=False)
class AuthenticationError(Exception):
    """Domain-specific error describing why authentication failed."""

    message: str
    code: str = "auth.invalid_token"
    status_code: int = status.HTTP_401_UNAUTHORIZED
    headers: Mapping[str, str] | None = None
    websocket_code: int = 4401

    def as_http_exception(self) -> HTTPException:
        """Translate the authentication error to an HTTPException."""
        headers = {"WWW-Authenticate": "Bearer"}
        if self.headers:
            headers.update(self.headers)
        detail = {"message": self.message, "code": self.code}
        return HTTPException(
            status_code=self.status_code,
            detail=detail,
            headers=headers,
        )


class JWKSCache:
    """Cache JWKS responses with respect to a configured TTL."""

    def __init__(self, fetcher: JWKSFetcher, ttl_seconds: int) -> None:
        self._fetcher = fetcher
        self._ttl = max(ttl_seconds, 0)
        self._lock = asyncio.Lock()
        self._jwks: list[Mapping[str, Any]] = []
        self._expires_at: datetime | None = None

    async def keys(self) -> list[Mapping[str, Any]]:
        """Return cached JWKS data, fetching when stale."""
        now = datetime.now(tz=UTC)
        if self._jwks and self._expires_at and now < self._expires_at:
            return self._jwks

        async with self._lock:
            if self._jwks and self._expires_at and now < self._expires_at:
                return self._jwks

            jwks, ttl = await self._fetcher()
            self._jwks = jwks
            effective_ttl = self._ttl
            if ttl is not None:
                header_ttl = max(ttl, 0)
                if effective_ttl > 0:
                    effective_ttl = min(effective_ttl, header_ttl)
                else:
                    effective_ttl = header_ttl
            if effective_ttl:
                self._expires_at = now + timedelta(seconds=effective_ttl)
            else:
                self._expires_at = None
            return self._jwks


class Authenticator:
    """Validate bearer tokens against service tokens or JWT configuration."""

    def __init__(self, settings: AuthSettings) -> None:
        """Create the authenticator using resolved configuration."""
        self._settings = settings
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
            if isinstance(algorithm_hint, str):
                algorithm_str = algorithm_hint
            else:
                algorithm_str = None
            self._static_jwks.append((jwk, algorithm_str))

    @property
    def settings(self) -> AuthSettings:
        """Expose the resolved settings."""
        return self._settings

    async def authenticate(self, token: str) -> RequestContext:
        """Validate a bearer token and return the associated identity."""
        if not token:
            raise AuthenticationError("Missing bearer token", code="auth.missing_token")

        identity = self._authenticate_service_token(token)
        if identity is not None:
            return identity

        if (
            self._settings.jwt_secret
            or self._settings.jwks_url
            or self._settings.jwks_static
        ):
            return await self._authenticate_jwt(token)

        raise AuthenticationError("Invalid bearer token", code="auth.invalid_token")

    def _authenticate_service_token(self, token: str) -> RequestContext | None:
        """Return a RequestContext for a matching service token."""
        if not self._settings.service_tokens:
            return None

        for record in self._settings.service_tokens:
            if record.matches(token):
                claims = {
                    "token_type": "service",
                    "token_id": record.identifier,
                    "scopes": sorted(record.scopes),
                    "workspace_ids": sorted(record.workspace_ids),
                }
                return RequestContext(
                    subject=record.identifier,
                    identity_type="service",
                    scopes=record.scopes,
                    workspace_ids=record.workspace_ids,
                    token_id=record.identifier,
                    claims=claims,
                )
        return None

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
            if isinstance(entry, Mapping):
                entry_algorithm = entry.get("alg")
            else:
                entry_algorithm = None
            if isinstance(entry_algorithm, str):
                algorithm_hint = entry_algorithm
            else:
                algorithm_hint = None
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
        issued_at = _parse_timestamp(claims.get("iat"))
        expires_at = _parse_timestamp(claims.get("exp"))
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


def _parse_timestamp(value: Any) -> datetime | None:
    """Convert UNIX timestamps or ISO strings to aware datetimes."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        try:
            if value.isdigit():
                return datetime.fromtimestamp(int(value), tz=UTC)
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:  # pragma: no cover - defensive
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


def _extract_scopes(claims: Mapping[str, Any]) -> Iterable[str]:
    """Normalize scope claim representations into an iterable of strings."""
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
        scopes.update(_coerce_str_items(candidate))
    return scopes


def _extract_workspace_ids(claims: Mapping[str, Any]) -> Iterable[str]:
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
        workspaces.update(_coerce_str_items(candidate))
    return workspaces


def _coerce_str_items(value: Any) -> set[str]:
    """Convert strings, iterables, or JSON payloads into a set of strings."""
    if value is None:
        return set()
    if isinstance(value, str):
        return _coerce_from_string(value)
    if isinstance(value, Mapping):
        return _coerce_from_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return _coerce_from_sequence(value)

    text = str(value).strip()
    return {text} if text else set()


def _parse_string_items(raw: str) -> Any:
    """Return structured data parsed from a string representation."""
    stripped = raw.strip()
    if not stripped:
        return []
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        parts = [part.strip() for part in stripped.replace(",", " ").split()]
        return [part for part in parts if part]


def _coerce_from_string(value: str) -> set[str]:
    parsed = _parse_string_items(value)
    if isinstance(parsed, list):
        items: set[str] = set()
        for item in parsed:
            if isinstance(item, str):
                token = item.strip()
                if token:
                    items.add(token)
            else:
                items.update(_coerce_str_items(item))
        return items
    return _coerce_str_items(parsed)


def _coerce_from_mapping(data: Mapping[str, Any]) -> set[str]:
    items: set[str] = set()
    for value in data.values():
        items.update(_coerce_str_items(value))
    return items


def _coerce_from_sequence(values: Sequence[Any]) -> set[str]:
    items: set[str] = set()
    for value in values:
        items.update(_coerce_str_items(value))
    return items


def _normalize_token_hash(value: str) -> str:
    """Normalize hashes stored with common prefixes."""
    candidate = value.strip()
    if not candidate:
        raise ValueError("Service token hash must not be empty")
    lowered = candidate.lower()
    if lowered.startswith("sha256:"):
        candidate = candidate.split(":", 1)[1]
    elif lowered.startswith("sha256$"):
        candidate = candidate.split("$", 1)[1]
    return candidate.lower()


def _service_token_from_mapping(data: Mapping[str, Any]) -> ServiceTokenRecord | None:
    """Create a ServiceTokenRecord from a mapping configuration entry."""
    raw_identifier = data.get("id") or data.get("identifier") or data.get("name") or ""
    identifier = str(raw_identifier).strip()
    secret_value = data.get("secret") or data.get("token") or data.get("value")
    hashed_value = data.get("hash") or data.get("hashed") or data.get("secret_hash")
    scopes = frozenset(_coerce_str_items(data.get("scopes")))
    workspaces = frozenset(_coerce_str_items(data.get("workspace_ids")))

    if hashed_value:
        try:
            token_hash = _normalize_token_hash(str(hashed_value))
        except ValueError:
            return None
        identifier = identifier or token_hash[:8]
        return ServiceTokenRecord(
            identifier=identifier,
            secret_hash=token_hash,
            scopes=scopes,
            workspace_ids=workspaces,
        )

    if not secret_value:
        return None

    token_hash = hashlib.sha256(str(secret_value).encode("utf-8")).hexdigest()
    identifier = identifier or token_hash[:8]
    return ServiceTokenRecord(
        identifier=identifier,
        secret_hash=token_hash,
        scopes=scopes,
        workspace_ids=workspaces,
    )


def _parse_service_tokens(raw: Any) -> list[ServiceTokenRecord]:
    """Parse service token configuration representations into records."""
    entries = _normalize_service_token_entries(raw)
    records: list[ServiceTokenRecord] = []
    for entry in entries:
        if isinstance(entry, ServiceTokenRecord):
            records.append(entry)
            continue
        record: ServiceTokenRecord | None
        if isinstance(entry, Mapping):
            record = _service_token_from_mapping(entry)
        else:
            text = str(entry).strip()
            if not text:
                continue
            token_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            record = ServiceTokenRecord(
                identifier=token_hash[:8],
                secret_hash=token_hash,
            )
        if record is not None:
            records.append(record)
    return records


def _normalize_service_token_entries(raw: Any) -> list[Any]:
    """Return a list of raw token entries derived from configuration values."""
    if raw is None:
        return []
    if isinstance(raw, ServiceTokenRecord):
        return [raw]
    if isinstance(raw, Mapping):
        return [raw]
    if isinstance(raw, str):
        return _normalize_service_tokens_from_string(raw)
    if isinstance(raw, Sequence) and not isinstance(raw, (bytes, bytearray, str)):
        items: list[Any] = []
        for item in raw:
            items.extend(_normalize_service_token_entries(item))
        return items
    return [raw]


def _normalize_service_tokens_from_string(value: str) -> list[Any]:
    stripped = value.strip()
    if not stripped:
        return []
    if stripped.startswith(("[", "{")):
        parsed = _parse_string_items(stripped)
        return _normalize_service_token_entries(parsed)
    if "," in stripped or " " in stripped:
        parsed = _parse_string_items(stripped)
        if isinstance(parsed, Sequence) and not isinstance(
            parsed, (bytes, bytearray, str)
        ):
            items: list[Any] = []
            for item in parsed:
                items.extend(_normalize_service_token_entries(item))
            return items
        return _normalize_service_token_entries(parsed)
    return [stripped]


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _coerce_mode(value: Any) -> str:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"disabled", "required", "optional"}:
            return lowered
    return "optional"


def _parse_float(value: Any, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return default


def _parse_int(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return default


def _parse_str_sequence(value: Any) -> tuple[str, ...]:
    items = _coerce_str_items(value)
    return tuple(item for item in items if item)


_DEFAULT_ALGORITHMS: tuple[str, ...] = ("RS256", "HS256")


def load_auth_settings(*, refresh: bool = False) -> AuthSettings:
    """Load authentication settings from Dynaconf and environment variables."""
    settings = get_settings(refresh=refresh)
    mode = _coerce_mode(settings.get("AUTH_MODE", "optional"))
    jwt_secret = _coerce_optional_str(settings.get("AUTH_JWT_SECRET"))
    jwks_url = _coerce_optional_str(settings.get("AUTH_JWKS_URL"))
    jwks_cache_ttl = _parse_int(settings.get("AUTH_JWKS_CACHE_TTL"), 300)
    jwks_timeout = _parse_float(settings.get("AUTH_JWKS_TIMEOUT"), 5.0)

    jwks_raw = settings.get("AUTH_JWKS") or settings.get("AUTH_JWKS_STATIC")
    jwks_static = tuple(dict(item) for item in (_parse_jwks(jwks_raw)))

    allowed_algorithms = _parse_str_sequence(settings.get("AUTH_ALLOWED_ALGORITHMS"))
    if not allowed_algorithms:
        allowed_algorithms = _DEFAULT_ALGORITHMS

    audiences = _parse_str_sequence(settings.get("AUTH_AUDIENCE"))
    issuer = _coerce_optional_str(settings.get("AUTH_ISSUER"))

    service_token_records = tuple(
        _parse_service_tokens(settings.get("AUTH_SERVICE_TOKENS"))
    )

    return AuthSettings(
        mode=mode,
        jwt_secret=jwt_secret,
        jwks_url=jwks_url,
        jwks_static=tuple(jwks_static),
        jwks_cache_ttl=jwks_cache_ttl,
        jwks_timeout=jwks_timeout,
        allowed_algorithms=tuple(allowed_algorithms),
        audiences=tuple(audiences),
        issuer=issuer,
        service_tokens=service_token_records,
    )


def _parse_jwks(raw: Any) -> list[Mapping[str, Any]]:
    """Parse JWKS configuration supporting string, mapping, or sequences."""
    data = raw
    if isinstance(raw, str):
        candidate = raw.strip()
        if not candidate:
            return []
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            logger.warning("Failed to parse AUTH_JWKS value as JSON")
            return []

    if isinstance(data, Mapping):
        keys = data.get("keys")
        return _normalize_jwk_list(keys)
    if isinstance(data, Sequence):
        return _normalize_jwk_list(data)
    return []


def _normalize_jwk_list(value: Any) -> list[Mapping[str, Any]]:
    """Return a normalized list of JWKS dictionaries."""
    if not isinstance(value, Sequence):
        return []
    normalized: list[Mapping[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            normalized.append(dict(item))
    return normalized


_authenticator_cache: dict[str, Authenticator | None] = {"authenticator": None}


def get_authenticator(*, refresh: bool = False) -> Authenticator:
    """Return a cached Authenticator instance, reloading settings when required."""
    if refresh:
        _authenticator_cache["authenticator"] = None
    authenticator = _authenticator_cache.get("authenticator")
    if authenticator is None:
        settings = load_auth_settings(refresh=refresh)
        authenticator = Authenticator(settings)
        _authenticator_cache["authenticator"] = authenticator
    return authenticator


def reset_authentication_state() -> None:
    """Clear cached authentication state and refresh Dynaconf settings."""
    _authenticator_cache["authenticator"] = None
    get_settings(refresh=True)


def _extract_bearer_token(header_value: str | None) -> str:
    if not header_value:
        raise AuthenticationError("Missing bearer token", code="auth.missing_token")
    parts = header_value.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError(
            "Authorization header must use the Bearer scheme",
            code="auth.invalid_scheme",
        )
    token = parts[1].strip()
    if not token:
        raise AuthenticationError("Missing bearer token", code="auth.missing_token")
    return token


async def authenticate_request(request: Request) -> RequestContext:
    """FastAPI dependency that enforces authentication on HTTP requests."""
    authenticator = get_authenticator()
    if not authenticator.settings.enforce:
        context = RequestContext.anonymous()
        request.state.auth = context
        return context

    try:
        token = _extract_bearer_token(request.headers.get("Authorization"))
        context = await authenticator.authenticate(token)
    except AuthenticationError as exc:
        raise exc.as_http_exception() from exc

    request.state.auth = context
    return context


async def authenticate_websocket(websocket: WebSocket) -> RequestContext:
    """Authenticate a WebSocket connection before accepting it."""
    authenticator = get_authenticator()
    if not authenticator.settings.enforce:
        context = RequestContext.anonymous()
        websocket.state.auth = context
        return context

    header_value = websocket.headers.get("authorization")
    token: str | None = None
    try:
        if header_value:
            token = _extract_bearer_token(header_value)
        else:
            query_params = websocket.query_params
            token_param = query_params.get("token") or query_params.get("access_token")
            if token_param:
                token = token_param
    except AuthenticationError as exc:
        await websocket.close(code=exc.websocket_code, reason=exc.message)
        raise

    if not token:
        await websocket.close(code=4401, reason="Missing bearer token")
        raise AuthenticationError("Missing bearer token", code="auth.missing_token")

    try:
        context = await authenticator.authenticate(token)
    except AuthenticationError as exc:
        await websocket.close(code=exc.websocket_code, reason=exc.message)
        raise

    websocket.state.auth = context
    return context


__all__ = [
    "AuthSettings",
    "AuthenticationError",
    "Authenticator",
    "RequestContext",
    "authenticate_request",
    "authenticate_websocket",
    "get_authenticator",
    "load_auth_settings",
    "reset_authentication_state",
]
