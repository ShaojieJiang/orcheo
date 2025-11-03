from __future__ import annotations
import asyncio
import hashlib
import hmac
import json
import logging
import secrets
from collections import Counter, deque
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
import httpx
import jwt
from fastapi import Depends, HTTPException, Request, WebSocket, status
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
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    rotation_expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
    rotated_to: str | None = None
    last_used_at: datetime | None = None
    use_count: int = 0

    def matches(self, token: str) -> bool:
        """Return True when the provided token matches the stored hash."""
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return hmac.compare_digest(self.secret_hash, digest)

    def is_revoked(self) -> bool:
        """Return True when the token has been revoked."""
        return self.revoked_at is not None

    def is_expired(self, *, now: datetime | None = None) -> bool:
        """Return True when the token has passed its expiry timestamp."""
        if self.expires_at is None:
            return False
        reference = now or datetime.now(tz=UTC)
        return reference >= self.expires_at

    def is_active(self, *, now: datetime | None = None) -> bool:
        """Return True when the token is neither expired nor revoked."""
        return not self.is_revoked() and not self.is_expired(now=now)


@dataclass(slots=True)
class AuthEvent:
    """Structured record describing an authentication-related event."""

    event: str
    status: Literal["success", "failure"]
    subject: str | None
    identity_type: str | None
    token_id: str | None
    ip: str | None = None
    detail: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


class AuthTelemetry:
    """Collect authentication audit events and counters in-memory."""

    def __init__(self, *, max_events: int = 512) -> None:
        """Initialise the telemetry sink with bounded storage."""
        self._events: deque[AuthEvent] = deque(maxlen=max_events)
        self._counters: Counter[str] = Counter()

    def record(self, event: AuthEvent) -> None:
        """Append an event to the audit log and increment counters."""
        self._events.append(event)
        counter_key = f"{event.event}:{event.status}"
        self._counters[counter_key] += 1

    def record_auth_success(
        self, context: RequestContext, *, ip: str | None = None
    ) -> None:
        """Record a successful authentication event."""
        self.record(
            AuthEvent(
                event="authenticate",
                status="success",
                subject=context.subject,
                identity_type=context.identity_type,
                token_id=context.token_id,
                ip=ip,
            )
        )

    def record_auth_failure(self, *, reason: str, ip: str | None = None) -> None:
        """Record a failed authentication attempt."""
        self.record(
            AuthEvent(
                event="authenticate",
                status="failure",
                subject=None,
                identity_type=None,
                token_id=None,
                ip=ip,
                detail=reason,
            )
        )

    def record_service_token_event(
        self, action: str, record: ServiceTokenRecord
    ) -> None:
        """Record lifecycle activity for a managed service token."""
        self.record(
            AuthEvent(
                event=f"service_token.{action}",
                status="success",
                subject=record.identifier,
                identity_type="service",
                token_id=record.identifier,
            )
        )

    def metrics(self) -> dict[str, int]:
        """Return a snapshot of aggregated counters."""
        return dict(self._counters)

    def events(self) -> tuple[AuthEvent, ...]:
        """Return recent authentication events in chronological order."""
        return tuple(self._events)

    def reset(self) -> None:
        """Clear stored events and counters."""
        self._events.clear()
        self._counters.clear()


auth_telemetry = AuthTelemetry()


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
    rate_limit_ip: int
    rate_limit_identity: int
    rate_limit_interval: int
    service_token_db_path: str | None
    bootstrap_service_token: str | None = None
    bootstrap_token_scopes: frozenset[str] = field(default_factory=frozenset)
    bootstrap_token_expires_at: datetime | None = None

    @property
    def enforce(self) -> bool:
        """Return True when authentication should be enforced for requests."""
        if self.mode == "disabled":
            return False
        if self.mode == "required":
            return True
        return bool(
            self.jwt_secret
            or self.jwks_url
            or self.jwks_static
            or self.service_token_db_path
            or self.bootstrap_service_token
        )


class SlidingWindowRateLimiter:
    """Maintain a sliding window rate limiter for authentication events."""

    def __init__(
        self,
        limit: int,
        interval_seconds: int,
        *,
        code: str,
        message_template: str,
    ) -> None:
        self._limit = max(int(limit), 0)
        self._interval = max(int(interval_seconds), 1)
        self._code = code
        self._message_template = message_template
        self._events: dict[str, deque[datetime]] = {}

    def hit(self, key: str, *, now: datetime | None = None) -> None:
        """Record an attempt and raise when the limit is exceeded."""
        if self._limit == 0 or not key:
            return

        timestamp = now or datetime.now(tz=UTC)
        window_start = timestamp - timedelta(seconds=self._interval)
        bucket = self._events.setdefault(key, deque())

        while bucket and bucket[0] <= window_start:
            bucket.popleft()

        if len(bucket) >= self._limit:
            message = self._message_template.format(
                key=key, limit=self._limit, interval=self._interval
            )
            raise AuthenticationError(
                message,
                code=self._code,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(self._interval)},
            )

        bucket.append(timestamp)

    def reset(self) -> None:
        """Clear stored rate limiting state."""
        self._events.clear()


class AuthRateLimiter:
    """Aggregate rate limiting for per-IP and per-identity enforcement."""

    def __init__(
        self, *, ip_limit: int, identity_limit: int, interval_seconds: int
    ) -> None:
        """Configure rate limits for per-IP and per-identity buckets."""
        self._ip = SlidingWindowRateLimiter(
            ip_limit,
            interval_seconds,
            code="auth.rate_limited.ip",
            message_template="Too many authentication attempts from IP {key}",
        )
        self._identity = SlidingWindowRateLimiter(
            identity_limit,
            interval_seconds,
            code="auth.rate_limited.identity",
            message_template="Too many authentication attempts for identity {key}",
        )

    def check_ip(self, ip: str | None, *, now: datetime | None = None) -> None:
        """Enforce the configured rate limit for an IP address."""
        if ip:
            self._ip.hit(ip, now=now)

    def check_identity(
        self, identity: str | None, *, now: datetime | None = None
    ) -> None:
        """Enforce the configured rate limit for an authenticated identity."""
        if identity:
            self._identity.hit(identity, now=now)

    def reset(self) -> None:
        """Reset internal counters for both limiters."""
        self._ip.reset()
        self._identity.reset()


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


class AuthorizationError(AuthenticationError):
    """Raised when an authenticated identity lacks required permissions."""

    status_code: int = status.HTTP_403_FORBIDDEN
    code: str = "auth.forbidden"
    websocket_code: int = 4403


class ServiceTokenManager:
    """Manage lifecycle of service tokens with database persistence."""

    def __init__(
        self,
        repository: Any,  # ServiceTokenRepository protocol
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize the manager with a token repository."""
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(tz=UTC))
        self._cache: dict[str, ServiceTokenRecord] = {}
        self._cache_expires_at: datetime | None = None
        self._cache_ttl = timedelta(seconds=30)

    async def _get_cache(self) -> dict[str, ServiceTokenRecord]:
        """Return cached active tokens, refreshing if stale."""
        now = self._clock()
        if self._cache and self._cache_expires_at and now < self._cache_expires_at:
            return self._cache

        active_records = await self._repository.list_active(now=now)
        self._cache = {record.identifier: record for record in active_records}
        self._cache_expires_at = now + self._cache_ttl
        return self._cache

    def _invalidate_cache(self) -> None:
        """Clear the token cache to force reload."""
        self._cache.clear()
        self._cache_expires_at = None

    async def all(self) -> tuple[ServiceTokenRecord, ...]:
        """Return all active service token records."""
        cache = await self._get_cache()
        return tuple(cache.values())

    async def authenticate(self, token: str) -> ServiceTokenRecord:
        """Return the record for ``token`` or raise an AuthenticationError."""
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        record = await self._repository.find_by_hash(digest)

        if record is None or not record.matches(token):
            raise AuthenticationError("Invalid bearer token", code="auth.invalid_token")

        check_time = self._clock()
        if record.is_revoked():
            raise AuthenticationError(
                "Service token has been revoked",
                code="auth.token_revoked",
                status_code=status.HTTP_403_FORBIDDEN,
            )
        if record.is_expired(now=check_time):
            raise AuthenticationError(
                "Service token has expired",
                code="auth.token_expired",
                status_code=status.HTTP_403_FORBIDDEN,
            )

        await self._repository.record_usage(record.identifier)
        usage_time = self._clock()
        updated_record = replace(
            record,
            last_used_at=usage_time,
            use_count=record.use_count + 1,
        )
        if record.identifier in self._cache:
            self._cache[record.identifier] = updated_record

        return updated_record

    async def mint(
        self,
        *,
        identifier: str | None = None,
        scopes: Iterable[str] = (),
        workspace_ids: Iterable[str] = (),
        expires_in: timedelta | int | None = None,
    ) -> tuple[str, ServiceTokenRecord]:
        """Mint a new service token and return the raw secret and record."""
        secret = secrets.token_urlsafe(32)
        digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
        now = self._clock()
        if expires_in is None:
            expires_at: datetime | None = None
        elif isinstance(expires_in, timedelta):
            expires_at = now + expires_in
        else:
            expires_at = now + timedelta(seconds=int(expires_in))

        record = ServiceTokenRecord(
            identifier=identifier or digest[:8],
            secret_hash=digest,
            scopes=frozenset(scopes),
            workspace_ids=frozenset(workspace_ids),
            issued_at=now,
            expires_at=expires_at,
        )
        await self._repository.create(record)
        await self._repository.record_audit_event(record.identifier, "created")
        self._invalidate_cache()
        auth_telemetry.record_service_token_event("mint", record)
        return secret, record

    async def rotate(
        self,
        identifier: str,
        *,
        overlap_seconds: int = 300,
        expires_in: timedelta | int | None = None,
    ) -> tuple[str, ServiceTokenRecord]:
        """Rotate ``identifier`` and return the replacement token."""
        record = await self._repository.find_by_id(identifier)
        if record is None:
            raise KeyError(identifier)

        now = self._clock()
        overlap = max(int(overlap_seconds), 0)
        secret, new_record = await self.mint(
            scopes=record.scopes,
            workspace_ids=record.workspace_ids,
            expires_in=expires_in,
        )
        rotation_expires_at = (
            now + timedelta(seconds=overlap) if overlap else record.rotation_expires_at
        )
        updated = replace(
            record,
            rotation_expires_at=rotation_expires_at,
            expires_at=self._calculate_rotation_expiry(record, now, overlap),
            rotated_to=new_record.identifier,
        )
        await self._repository.update(updated)
        await self._repository.record_audit_event(identifier, "rotated")
        self._invalidate_cache()
        auth_telemetry.record_service_token_event("rotate", updated)
        return secret, new_record

    async def revoke(
        self, identifier: str, *, reason: str | None = None
    ) -> ServiceTokenRecord:
        """Revoke ``identifier`` immediately and return the updated record."""
        record = await self._repository.find_by_id(identifier)
        if record is None:
            raise KeyError(identifier)
        updated = replace(
            record,
            revoked_at=self._clock(),
            revocation_reason=reason,
        )
        await self._repository.update(updated)
        await self._repository.record_audit_event(
            identifier, "revoked", details={"reason": reason} if reason else None
        )
        self._invalidate_cache()
        auth_telemetry.record_service_token_event("revoke", updated)
        return updated

    @staticmethod
    def _calculate_rotation_expiry(
        record: ServiceTokenRecord, now: datetime, overlap_seconds: int
    ) -> datetime | None:
        if overlap_seconds == 0:
            return record.expires_at
        overlap_expiry = now + timedelta(seconds=overlap_seconds)
        if record.expires_at is None:
            return overlap_expiry
        return min(record.expires_at, overlap_expiry)


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
            if isinstance(algorithm_hint, str):
                algorithm_str = algorithm_hint
            else:
                algorithm_str = None
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
        """Return a RequestContext for a matching service token."""
        # First check database-persisted tokens
        all_tokens = await self._token_manager.all()
        if all_tokens:
            try:
                record = await self._token_manager.authenticate(token)
                claims = {
                    "token_type": "service",
                    "token_id": record.identifier,
                    "scopes": sorted(record.scopes),
                    "workspace_ids": sorted(record.workspace_ids),
                    "rotated_to": record.rotated_to,
                    "revoked_at": record.revoked_at.isoformat()
                    if record.revoked_at
                    else None,
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
            except AuthenticationError as exc:
                if exc.code == "auth.invalid_token":
                    pass  # Fall through to check bootstrap token
                else:
                    raise

        # Check bootstrap service token from environment
        bootstrap_token = self._settings.bootstrap_service_token
        if bootstrap_token and hmac.compare_digest(token, bootstrap_token):
            expires_at = self._settings.bootstrap_token_expires_at
            if expires_at and datetime.now(tz=UTC) >= expires_at:
                logger.warning(
                    "Bootstrap service token has expired and will be rejected",
                )
                auth_telemetry.record_auth_failure(
                    reason="bootstrap_service_token_expired"
                )
                raise AuthenticationError(
                    "Bootstrap service token has expired",
                    code="auth.token_expired",
                )
            logger.info(
                "Bootstrap service token authenticated. "
                "Consider creating persistent tokens and removing the bootstrap token."
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
                workspace_ids=frozenset(),  # No workspace restrictions for bootstrap
                token_id="bootstrap",
                issued_at=None,
                expires_at=expires_at,
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
            else:  # pragma: no cover
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
    result: datetime | None = None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            result = value.replace(tzinfo=UTC)
        else:
            result = value.astimezone(UTC)
    elif isinstance(value, int | float):
        result = datetime.fromtimestamp(value, tz=UTC)
    elif isinstance(value, str):
        try:
            if value.isdigit():
                result = datetime.fromtimestamp(int(value), tz=UTC)
            else:
                result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:  # pragma: no cover - defensive
            result = None
    return result


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
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | str):
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
    if isinstance(value, int | float):
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

    # Service tokens are now stored in database
    service_token_db_path = _coerce_optional_str(
        settings.get("AUTH_SERVICE_TOKEN_DB_PATH")
    )
    if not service_token_db_path:
        # Default to same directory as workflow repository
        repo_path = settings.get("ORCHEO_REPOSITORY_SQLITE_PATH")
        if repo_path:
            from pathlib import Path

            db_path = Path(repo_path).expanduser()
            service_token_db_path = str(db_path.parent / "service_tokens.sqlite")

    rate_limit_ip = _parse_int(settings.get("AUTH_RATE_LIMIT_IP"), 0)
    rate_limit_identity = _parse_int(settings.get("AUTH_RATE_LIMIT_IDENTITY"), 0)
    rate_limit_interval = _parse_int(settings.get("AUTH_RATE_LIMIT_INTERVAL"), 60)

    # Bootstrap service token for initial token creation
    bootstrap_service_token = _coerce_optional_str(
        settings.get("AUTH_BOOTSTRAP_SERVICE_TOKEN")
    )
    bootstrap_token_scopes_raw = settings.get("AUTH_BOOTSTRAP_TOKEN_SCOPES")
    if bootstrap_token_scopes_raw:
        bootstrap_token_scopes = frozenset(
            _parse_str_sequence(bootstrap_token_scopes_raw)
        )
    else:
        # Default to full admin access for bootstrap token
        bootstrap_token_scopes = frozenset(
            [
                "admin:tokens:read",
                "admin:tokens:write",
                "workflows:read",
                "workflows:write",
                "workflows:execute",
                "vault:read",
                "vault:write",
            ]
        )

    bootstrap_token_expires_at_raw = settings.get("AUTH_BOOTSTRAP_TOKEN_EXPIRES_AT")
    bootstrap_token_expires_at = _parse_timestamp(bootstrap_token_expires_at_raw)
    if bootstrap_token_expires_at_raw and bootstrap_token_expires_at is None:
        logger.warning(
            "AUTH_BOOTSTRAP_TOKEN_EXPIRES_AT could not be parsed; expected ISO 8601 or "
            "UNIX timestamp"
        )

    if bootstrap_service_token:
        logger.warning(
            "Bootstrap service token is configured. This should only be used for "
            "initial setup and should be removed after creating persistent tokens."
        )

    if mode == "required" and not (
        jwt_secret
        or jwks_url
        or jwks_static
        or service_token_db_path
        or bootstrap_service_token
    ):
        logger.warning(
            "AUTH_MODE=required but no authentication credentials are configured; "
            "all requests will be rejected",
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
        service_token_db_path=service_token_db_path,
        bootstrap_service_token=bootstrap_service_token,
        bootstrap_token_scopes=bootstrap_token_scopes,
        bootstrap_token_expires_at=bootstrap_token_expires_at,
        rate_limit_ip=rate_limit_ip,
        rate_limit_identity=rate_limit_identity,
        rate_limit_interval=rate_limit_interval,
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
_auth_rate_limiter_cache: dict[str, AuthRateLimiter | None] = {"limiter": None}
_token_manager_cache: dict[str, ServiceTokenManager | None] = {"manager": None}


def get_authenticator(*, refresh: bool = False) -> Authenticator:
    """Return a cached Authenticator instance, reloading settings when required."""
    if refresh:
        _authenticator_cache["authenticator"] = None
        _auth_rate_limiter_cache["limiter"] = None
        _token_manager_cache["manager"] = None
    authenticator = _authenticator_cache.get("authenticator")
    if authenticator is None:
        settings = load_auth_settings(refresh=refresh)

        # Import here to avoid circular dependency
        from orcheo_backend.app.service_token_repository import (
            InMemoryServiceTokenRepository,
            SqliteServiceTokenRepository,
        )

        # Create repository based on configuration
        if settings.service_token_db_path:
            repository: Any = SqliteServiceTokenRepository(
                settings.service_token_db_path
            )
        else:
            repository = InMemoryServiceTokenRepository()

        # Create token manager with repository
        token_manager = ServiceTokenManager(repository)
        _token_manager_cache["manager"] = token_manager

        # Create authenticator with settings and token manager
        authenticator = Authenticator(settings, token_manager)
        _authenticator_cache["authenticator"] = authenticator
        _auth_rate_limiter_cache["limiter"] = AuthRateLimiter(
            ip_limit=settings.rate_limit_ip,
            identity_limit=settings.rate_limit_identity,
            interval_seconds=settings.rate_limit_interval,
        )
    return authenticator


def get_service_token_manager(*, refresh: bool = False) -> ServiceTokenManager:
    """Return the cached ServiceTokenManager instance."""
    if refresh:
        _token_manager_cache["manager"] = None
    # Ensure authenticator is initialized (which initializes token manager)
    get_authenticator(refresh=refresh)
    manager = _token_manager_cache.get("manager")
    if manager is None:
        raise RuntimeError("ServiceTokenManager not initialized")
    return manager


def get_auth_rate_limiter(*, refresh: bool = False) -> AuthRateLimiter:
    """Return the configured authentication rate limiter."""
    if refresh:
        _auth_rate_limiter_cache["limiter"] = None
    limiter = _auth_rate_limiter_cache.get("limiter")
    if limiter is None:
        settings = load_auth_settings(refresh=refresh)
        limiter = AuthRateLimiter(
            ip_limit=settings.rate_limit_ip,
            identity_limit=settings.rate_limit_identity,
            interval_seconds=settings.rate_limit_interval,
        )
        _auth_rate_limiter_cache["limiter"] = limiter
    return limiter


def reset_authentication_state() -> None:
    """Clear cached authentication state and refresh Dynaconf settings."""
    _authenticator_cache["authenticator"] = None
    _auth_rate_limiter_cache["limiter"] = None
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
        raise AuthenticationError(
            "Missing bearer token", code="auth.missing_token"
        )  # pragma: no cover - defensive
    return token


async def authenticate_request(request: Request) -> RequestContext:
    """FastAPI dependency that enforces authentication on HTTP requests."""
    authenticator = get_authenticator()
    if not authenticator.settings.enforce:
        context = RequestContext.anonymous()
        request.state.auth = context
        return context

    limiter = get_auth_rate_limiter()
    ip = request.client.host if request.client else None
    now = datetime.now(tz=UTC)
    try:
        limiter.check_ip(ip, now=now)
    except AuthenticationError as exc:
        raise exc.as_http_exception() from exc

    try:
        token = _extract_bearer_token(request.headers.get("Authorization"))
        context = await authenticator.authenticate(token)
    except AuthenticationError as exc:
        auth_telemetry.record_auth_failure(reason=exc.code, ip=ip)
        raise exc.as_http_exception() from exc

    try:
        limiter.check_identity(context.token_id or context.subject, now=now)
    except AuthenticationError as exc:
        raise exc.as_http_exception() from exc
    auth_telemetry.record_auth_success(context, ip=ip)
    request.state.auth = context
    return context


async def authenticate_websocket(websocket: WebSocket) -> RequestContext:
    """Authenticate a WebSocket connection before accepting it."""
    authenticator = get_authenticator()
    if not authenticator.settings.enforce:
        context = RequestContext.anonymous()
        websocket.state.auth = context
        return context

    limiter = get_auth_rate_limiter()
    ip = websocket.client.host if websocket.client else None
    now = datetime.now(tz=UTC)
    try:
        limiter.check_ip(ip, now=now)
    except AuthenticationError as exc:
        auth_telemetry.record_auth_failure(reason=exc.code, ip=ip)
        await websocket.close(code=exc.websocket_code, reason=exc.message)
        raise

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
        auth_telemetry.record_auth_failure(reason=exc.code, ip=ip)
        await websocket.close(code=exc.websocket_code, reason=exc.message)
        raise

    if not token:
        auth_telemetry.record_auth_failure(reason="auth.missing_token", ip=ip)
        await websocket.close(code=4401, reason="Missing bearer token")
        raise AuthenticationError("Missing bearer token", code="auth.missing_token")

    try:
        context = await authenticator.authenticate(token)
    except AuthenticationError as exc:
        auth_telemetry.record_auth_failure(reason=exc.code, ip=ip)
        await websocket.close(code=exc.websocket_code, reason=exc.message)
        raise

    try:
        limiter.check_identity(context.token_id or context.subject, now=now)
    except AuthenticationError as exc:
        auth_telemetry.record_auth_failure(reason=exc.code, ip=ip)
        await websocket.close(code=exc.websocket_code, reason=exc.message)
        raise
    auth_telemetry.record_auth_success(context, ip=ip)
    websocket.state.auth = context
    return context


class AuthorizationPolicy:
    """Evaluate authorization decisions based on a request context."""

    def __init__(self, context: RequestContext) -> None:
        """Bind the policy to the authenticated request context."""
        self._context = context

    @property
    def context(self) -> RequestContext:
        """Return the underlying request context."""
        return self._context

    def require_authenticated(self) -> RequestContext:
        """Ensure the request is associated with an authenticated identity."""
        if not self._context.is_authenticated:
            raise AuthenticationError(
                "Authentication required",
                code="auth.authentication_required",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return self._context

    def require_scopes(self, *scopes: str) -> RequestContext:
        """Ensure the identity possesses the provided scopes."""
        ensure_scopes(self._context, scopes)
        return self._context

    def require_workspace(self, workspace_id: str) -> RequestContext:
        """Ensure the identity is authorised for the workspace."""
        ensure_workspace_access(self._context, [workspace_id])
        return self._context

    def require_workspaces(self, workspace_ids: Iterable[str]) -> RequestContext:
        """Ensure the identity can access all provided workspaces."""
        ensure_workspace_access(self._context, workspace_ids)
        return self._context


async def get_request_context(request: Request) -> RequestContext:
    """Retrieve the RequestContext associated with the current request."""
    context = getattr(request.state, "auth", None)
    if isinstance(context, RequestContext):
        return context
    return await authenticate_request(request)


def get_authorization_policy(
    context: RequestContext = Depends(get_request_context),  # noqa: B008
) -> AuthorizationPolicy:
    """Return an AuthorizationPolicy bound to the active request context."""
    return AuthorizationPolicy(context)


def ensure_scopes(context: RequestContext, scopes: Iterable[str]) -> None:
    """Ensure the request context possesses all required scopes."""
    missing = [scope for scope in scopes if scope and scope not in context.scopes]
    if missing:
        raise AuthorizationError(
            "Missing required scopes: " + ", ".join(sorted(missing)),
            code="auth.missing_scope",
        )


def ensure_workspace_access(
    context: RequestContext, workspace_ids: Iterable[str]
) -> None:
    """Ensure the context is authorized for the requested workspace identifiers."""
    required = {workspace_id for workspace_id in workspace_ids if workspace_id}
    if not required:
        return
    if not context.workspace_ids:
        raise AuthorizationError(
            "Workspace access denied", code="auth.workspace_forbidden"
        )
    if not required.issubset(context.workspace_ids):
        missing = sorted(required.difference(context.workspace_ids))
        raise AuthorizationError(
            "Workspace access denied for: " + ", ".join(missing),
            code="auth.workspace_forbidden",
        )


def require_scopes(*scopes: str) -> Callable[..., Awaitable[RequestContext]]:
    """Return a FastAPI dependency that enforces required scopes."""

    async def dependency(
        context: RequestContext = Depends(get_request_context),  # noqa: B008
    ) -> RequestContext:
        ensure_scopes(context, scopes)
        return context

    return dependency


def require_workspace_access(
    *workspace_ids: str,
) -> Callable[..., Awaitable[RequestContext]]:
    """Return a dependency that ensures the caller may access the workspace."""

    async def dependency(
        context: RequestContext = Depends(get_request_context),  # noqa: B008
    ) -> RequestContext:
        ensure_workspace_access(context, workspace_ids)
        return context

    return dependency


__all__ = [
    "AuthEvent",
    "AuthRateLimiter",
    "AuthTelemetry",
    "AuthSettings",
    "AuthenticationError",
    "AuthorizationError",
    "AuthorizationPolicy",
    "Authenticator",
    "RequestContext",
    "ServiceTokenManager",
    "ServiceTokenRecord",
    "auth_telemetry",
    "authenticate_request",
    "authenticate_websocket",
    "ensure_scopes",
    "ensure_workspace_access",
    "get_authorization_policy",
    "get_auth_rate_limiter",
    "get_authenticator",
    "get_request_context",
    "get_service_token_manager",
    "load_auth_settings",
    "require_scopes",
    "require_workspace_access",
    "reset_authentication_state",
]
