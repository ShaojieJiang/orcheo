"""Tests for the FastAPI authentication dependencies."""

from __future__ import annotations
import hashlib
import logging
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from orcheo_backend.app import create_app
from orcheo_backend.app.authentication import (
    AuthenticationError,
    AuthorizationError,
    AuthorizationPolicy,
    JWKSCache,
    RequestContext,
    ServiceTokenManager,
    ServiceTokenRecord,
    auth_telemetry,
    authenticate_request,
    ensure_scopes,
    ensure_workspace_access,
    load_auth_settings,
    require_scopes,
    require_workspace_access,
    reset_authentication_state,
)
from orcheo_backend.app.repository import InMemoryWorkflowRepository
from orcheo_backend.app.service_token_repository import (
    InMemoryServiceTokenRepository,
    SqliteServiceTokenRepository,
)


@pytest.fixture(autouse=True)
def _reset_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure authentication state is cleared between tests."""

    for key in (
        "ORCHEO_AUTH_SERVICE_TOKENS",
        "ORCHEO_AUTH_JWT_SECRET",
        "ORCHEO_AUTH_MODE",
        "ORCHEO_AUTH_ALLOWED_ALGORITHMS",
        "ORCHEO_AUTH_AUDIENCE",
        "ORCHEO_AUTH_ISSUER",
        "ORCHEO_AUTH_JWKS_URL",
        "ORCHEO_AUTH_JWKS",
        "ORCHEO_SERVICE_TOKEN",
        "ORCHEO_AUTH_RATE_LIMIT_IP",
        "ORCHEO_AUTH_RATE_LIMIT_IDENTITY",
        "ORCHEO_AUTH_RATE_LIMIT_INTERVAL",
        "ORCHEO_AUTH_SERVICE_TOKEN_DB_PATH",
        "ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN",
        "ORCHEO_AUTH_BOOTSTRAP_TOKEN_SCOPES",
        "ORCHEO_AUTH_BOOTSTRAP_TOKEN_EXPIRES_AT",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_authentication_state()
    auth_telemetry.reset()
    yield
    monkeypatch.undo()
    reset_authentication_state()
    auth_telemetry.reset()


def _client() -> TestClient:
    repository = InMemoryWorkflowRepository()
    return TestClient(create_app(repository=repository))


def _setup_service_token(
    monkeypatch: pytest.MonkeyPatch,
    token_secret: str,
    *,
    identifier: str | None = None,
    scopes: list[str] | None = None,
    workspace_ids: list[str] | None = None,
    expires_at: datetime | None = None,
) -> tuple[str, str]:
    """Set up a service token for testing.

    Returns (db_path, token_secret) for use in tests.
    """
    # Create temporary database
    temp_dir = tempfile.mkdtemp()
    db_path = str(Path(temp_dir) / "test_tokens.sqlite")

    # Set up the database path env var
    monkeypatch.setenv("ORCHEO_AUTH_SERVICE_TOKEN_DB_PATH", db_path)

    # Create repository to ensure schema exists
    _ = SqliteServiceTokenRepository(db_path)

    # Create the token record
    token_hash = hashlib.sha256(token_secret.encode("utf-8")).hexdigest()
    record = ServiceTokenRecord(
        identifier=identifier or "test-token",
        secret_hash=token_hash,
        scopes=frozenset(scopes or []),
        workspace_ids=frozenset(workspace_ids or []),
        issued_at=datetime.now(tz=UTC),
        expires_at=expires_at,
    )

    # Store the token synchronously via direct SQLite access
    import json
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO service_tokens (
            identifier, secret_hash, scopes, workspace_ids,
            created_at, issued_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identifier,
            record.secret_hash,
            json.dumps(sorted(record.scopes)) if record.scopes else None,
            json.dumps(sorted(record.workspace_ids)) if record.workspace_ids else None,
            datetime.now(tz=UTC).isoformat(),
            record.issued_at.isoformat() if record.issued_at else None,
            record.expires_at.isoformat() if record.expires_at else None,
        ),
    )
    conn.commit()
    conn.close()

    return db_path, token_secret


def test_requests_allowed_when_auth_disabled() -> None:
    """Requests succeed when no authentication configuration is provided."""

    client = _client()
    response = client.get("/api/workflows")
    assert response.status_code == 200


def test_service_token_required_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing Authorization header yields 401 when service tokens are configured."""

    _setup_service_token(monkeypatch, "secret-token")
    reset_authentication_state()

    client = _client()
    response = client.get("/api/workflows")

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    detail = response.json()["detail"]
    assert detail["code"] == "auth.missing_token"


def test_valid_service_token_allows_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """Providing a valid service token authorizes the request."""

    _setup_service_token(monkeypatch, "ci-token", identifier="ci")
    reset_authentication_state()

    client = _client()
    response = client.get(
        "/api/workflows",
        headers={"Authorization": "Bearer ci-token"},
    )

    assert response.status_code == 200


def test_invalid_service_token_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Incorrect service tokens result in a 401 response."""

    _setup_service_token(monkeypatch, "ci-token", identifier="ci")
    reset_authentication_state()

    client = _client()
    response = client.get(
        "/api/workflows",
        headers={"Authorization": "Bearer not-valid"},
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "auth.invalid_token"


def test_jwt_secret_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT secrets allow bearer token authentication."""

    secret = "jwt-secret"
    monkeypatch.setenv("ORCHEO_AUTH_JWT_SECRET", secret)
    reset_authentication_state()

    now = datetime.now(tz=UTC)
    token = jwt.encode(
        {
            "sub": "tester",
            "scope": "workflows:read",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )

    client = _client()
    response = client.get(
        "/api/workflows",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


def test_jwt_missing_token_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configured JWT secret still enforces bearer tokens."""

    monkeypatch.setenv("ORCHEO_AUTH_JWT_SECRET", "jwt-secret")
    reset_authentication_state()

    client = _client()
    response = client.get("/api/workflows")

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "auth.missing_token"


@pytest.mark.asyncio
async def test_authenticate_request_sets_request_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """authenticate_request attaches the resolved context to the request state."""

    _setup_service_token(
        monkeypatch,
        "token-123",
        identifier="ci",
        scopes=["workflows:read"],
        workspace_ids=["ws-1"],
    )
    reset_authentication_state()

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"authorization", b"Bearer token-123")],
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request"}

    request = Request(scope, receive)  # type: ignore[arg-type]

    context = await authenticate_request(request)

    assert context.identity_type == "service"
    assert "workflows:read" in context.scopes
    assert request.state.auth is context


@pytest.mark.asyncio
async def test_jwks_cache_uses_shorter_header_ttl() -> None:
    """The JWKS cache honours a shorter Cache-Control max-age."""

    fetch_count = 0

    async def fetcher() -> tuple[list[dict[str, str]], int | None]:
        nonlocal fetch_count
        fetch_count += 1
        return ([{"kid": "key-1"}], 60)

    cache = JWKSCache(fetcher, ttl_seconds=300)

    keys = await cache.keys()

    assert keys == [{"kid": "key-1"}]
    assert fetch_count == 1
    assert cache._expires_at is not None  # noqa: SLF001 - accessed for verification only

    remaining = (cache._expires_at - datetime.now(tz=UTC)).total_seconds()
    assert remaining == pytest.approx(60, abs=1.0)


@pytest.mark.asyncio
async def test_jwks_cache_caps_ttl_to_configured_default() -> None:
    """The cache does not exceed the configured TTL when headers allow longer."""

    async def fetcher() -> tuple[list[dict[str, str]], int | None]:
        return ([{"kid": "key-1"}], 600)

    cache = JWKSCache(fetcher, ttl_seconds=120)

    await cache.keys()

    assert cache._expires_at is not None  # noqa: SLF001 - accessed for verification only
    remaining = (cache._expires_at - datetime.now(tz=UTC)).total_seconds()
    assert remaining == pytest.approx(120, abs=1.0)


@pytest.mark.asyncio
async def test_jwks_cache_refetches_when_header_disables_caching() -> None:
    """A header with max-age=0 forces the cache to refetch on every call."""

    fetch_count = 0

    async def fetcher() -> tuple[list[dict[str, str]], int | None]:
        nonlocal fetch_count
        fetch_count += 1
        return ([{"kid": "key-1"}], 0)

    cache = JWKSCache(fetcher, ttl_seconds=120)

    await cache.keys()
    assert cache._expires_at is None  # noqa: SLF001 - accessed for verification only

    await cache.keys()

    assert fetch_count == 2


def test_raw_service_token_emits_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Using raw service token secrets emits an operator-facing warning.

    NOTE: This test is no longer relevant with database-backed tokens,
    but kept for backwards compatibility. The warning is now only relevant
    when creating tokens via the API.
    """
    # With database-backed tokens, there's no concept of raw tokens in config
    # This test now verifies that loading auth settings without tokens works fine
    caplog.set_level(logging.WARNING)

    load_auth_settings(refresh=True)

    # No warnings should be emitted for missing tokens (this is valid config)
    assert not any("raw secret" in record.message for record in caplog.records)


def test_required_mode_without_credentials_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Enforcing authentication without credentials warns operators."""

    monkeypatch.setenv("ORCHEO_AUTH_MODE", "required")
    caplog.set_level(logging.WARNING)

    load_auth_settings(refresh=True)

    assert any(
        "no authentication credentials" in record.message for record in caplog.records
    )


def test_ensure_scopes_allows_present_scopes() -> None:
    """ensure_scopes succeeds when all required scopes are present."""

    context = RequestContext(
        subject="svc",
        identity_type="service",
        scopes=frozenset({"workflows:read", "workflows:write"}),
    )

    ensure_scopes(context, ["workflows:read"])


def test_ensure_scopes_raises_on_missing_scope() -> None:
    """ensure_scopes raises AuthorizationError when scopes are missing."""

    context = RequestContext(
        subject="svc",
        identity_type="service",
        scopes=frozenset({"workflows:read"}),
    )

    with pytest.raises(AuthorizationError) as exc:
        ensure_scopes(context, ["workflows:write"])

    assert "Missing required scopes" in str(exc.value)


def test_ensure_workspace_access_allows_subset() -> None:
    """Callers with matching workspace IDs pass the authorization check."""

    context = RequestContext(
        subject="svc",
        identity_type="service",
        workspace_ids=frozenset({"ws-1", "ws-2"}),
    )

    ensure_workspace_access(context, ["ws-2"])


def test_ensure_workspace_access_raises_for_missing_workspace() -> None:
    """Missing workspace authorization raises AuthorizationError."""

    context = RequestContext(
        subject="svc",
        identity_type="service",
        workspace_ids=frozenset({"ws-1"}),
    )

    with pytest.raises(AuthorizationError):
        ensure_workspace_access(context, ["ws-2"])


def test_authorization_policy_enforces_scopes_and_workspaces() -> None:
    """AuthorizationPolicy should gate scopes and workspace access."""

    context = RequestContext(
        subject="user-1",
        identity_type="user",
        scopes=frozenset({"chatkit:session"}),
        workspace_ids=frozenset({"ws-1"}),
    )
    policy = AuthorizationPolicy(context)

    assert policy.require_authenticated() is context
    assert policy.require_scopes("chatkit:session") is context
    assert policy.require_workspace("ws-1") is context

    with pytest.raises(AuthorizationError):
        policy.require_workspace("ws-2")


@pytest.mark.asyncio
async def test_service_token_manager_mint_rotate_revoke() -> None:
    """ServiceTokenManager should support rotation with overlap and revocation."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)
    secret, record = await manager.mint(
        scopes={"workflows:read"}, workspace_ids={"ws-1"}
    )

    assert record.matches(secret)
    all_tokens = await manager.all()
    assert record.identifier in {item.identifier for item in all_tokens}

    overlap_secret, rotated = await manager.rotate(
        record.identifier, overlap_seconds=60
    )
    authenticated = await manager.authenticate(secret)
    assert authenticated.identifier == record.identifier

    await manager.revoke(rotated.identifier, reason="test")
    with pytest.raises(AuthenticationError):
        await manager.authenticate(overlap_secret)


@pytest.mark.asyncio
async def test_require_scopes_dependency_enforces_missing_scope() -> None:
    """require_scopes integrates with authenticate_request for FastAPI routes."""

    dependency = require_scopes("workflows:write")
    context = RequestContext(
        subject="svc",
        identity_type="service",
        scopes=frozenset({"workflows:read"}),
    )

    with pytest.raises(AuthorizationError):
        await dependency(context)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_require_workspace_access_dependency_allows_valid_context() -> None:
    """require_workspace_access allows contexts authorized for the workspace."""

    dependency = require_workspace_access("ws-1")
    context = RequestContext(
        subject="svc",
        identity_type="service",
        workspace_ids=frozenset({"ws-1", "ws-2"}),
    )

    result = await dependency(context)  # type: ignore[arg-type]

    assert result is context


def test_authenticate_request_records_audit_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful authentication should emit audit telemetry events."""

    _setup_service_token(
        monkeypatch,
        "token-abc",
        identifier="ci",
        scopes=["workflows:read"],
    )
    reset_authentication_state()
    auth_telemetry.reset()

    client = _client()
    response = client.get(
        "/api/workflows",
        headers={"Authorization": "Bearer token-abc"},
    )
    assert response.status_code == 200
    events = auth_telemetry.events()
    assert any(event.status == "success" for event in events)


def test_authenticate_request_rate_limits_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exceeding the configured per-IP limit should yield a 429 error."""

    _setup_service_token(
        monkeypatch,
        "token-xyz",
        identifier="ci",
        scopes=["workflows:read"],
    )
    monkeypatch.setenv("ORCHEO_AUTH_RATE_LIMIT_IP", "2")
    monkeypatch.setenv("ORCHEO_AUTH_RATE_LIMIT_IDENTITY", "5")
    reset_authentication_state()

    client = _client()
    headers = {"Authorization": "Bearer token-xyz"}
    assert client.get("/api/workflows", headers=headers).status_code == 200
    assert client.get("/api/workflows", headers=headers).status_code == 200
    response = client.get("/api/workflows", headers=headers)

    assert response.status_code == 429
    detail = response.json()["detail"]
    assert detail["code"] == "auth.rate_limited.ip"


def test_authenticate_request_rate_limits_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exceeding the configured per-identity limit should yield a 429 error."""

    _setup_service_token(
        monkeypatch,
        "token-identity",
        identifier="ci",
        scopes=["workflows:read"],
    )
    monkeypatch.setenv("ORCHEO_AUTH_RATE_LIMIT_IP", "10")
    monkeypatch.setenv("ORCHEO_AUTH_RATE_LIMIT_IDENTITY", "2")
    reset_authentication_state()

    client = _client()
    headers = {"Authorization": "Bearer token-identity"}
    assert client.get("/api/workflows", headers=headers).status_code == 200
    assert client.get("/api/workflows", headers=headers).status_code == 200
    response = client.get("/api/workflows", headers=headers)

    assert response.status_code == 429
    detail = response.json()["detail"]
    assert detail["code"] == "auth.rate_limited.identity"


# RequestContext tests
def test_request_context_anonymous() -> None:
    """RequestContext.anonymous() creates an anonymous context."""

    context = RequestContext.anonymous()

    assert context.subject == "anonymous"
    assert context.identity_type == "anonymous"
    assert not context.is_authenticated
    assert not context.has_scope("any-scope")


def test_request_context_is_authenticated() -> None:
    """is_authenticated returns True for non-anonymous contexts."""

    context = RequestContext(subject="user-123", identity_type="user")

    assert context.is_authenticated


def test_request_context_has_scope() -> None:
    """has_scope checks if a scope is present."""

    context = RequestContext(
        subject="svc",
        identity_type="service",
        scopes=frozenset({"workflows:read", "workflows:write"}),
    )

    assert context.has_scope("workflows:read")
    assert not context.has_scope("workflows:delete")


# ServiceTokenRecord tests
def test_service_token_record_matches() -> None:
    """ServiceTokenRecord.matches() validates tokens against the hash."""
    import hashlib
    from orcheo_backend.app.authentication import ServiceTokenRecord

    token = "my-secret-token"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    record = ServiceTokenRecord(identifier="test", secret_hash=digest)

    assert record.matches(token)
    assert not record.matches("wrong-token")


def test_service_token_record_is_revoked() -> None:
    """ServiceTokenRecord.is_revoked() checks revocation status."""
    from orcheo_backend.app.authentication import ServiceTokenRecord

    record = ServiceTokenRecord(identifier="test", secret_hash="hash123")
    assert not record.is_revoked()

    revoked_record = ServiceTokenRecord(
        identifier="test",
        secret_hash="hash123",
        revoked_at=datetime.now(tz=UTC),
    )
    assert revoked_record.is_revoked()


def test_service_token_record_is_expired() -> None:
    """ServiceTokenRecord.is_expired() checks expiry status."""
    from orcheo_backend.app.authentication import ServiceTokenRecord

    # No expiry
    record = ServiceTokenRecord(identifier="test", secret_hash="hash123")
    assert not record.is_expired()

    # Expired
    expired_record = ServiceTokenRecord(
        identifier="test",
        secret_hash="hash123",
        expires_at=datetime.now(tz=UTC) - timedelta(hours=1),
    )
    assert expired_record.is_expired()

    # Not yet expired
    future_record = ServiceTokenRecord(
        identifier="test",
        secret_hash="hash123",
        expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
    )
    assert not future_record.is_expired()


def test_service_token_record_is_active() -> None:
    """ServiceTokenRecord.is_active() combines revocation and expiry checks."""
    from orcheo_backend.app.authentication import ServiceTokenRecord

    # Active
    record = ServiceTokenRecord(
        identifier="test",
        secret_hash="hash123",
        expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
    )
    assert record.is_active()

    # Revoked
    revoked_record = ServiceTokenRecord(
        identifier="test",
        secret_hash="hash123",
        revoked_at=datetime.now(tz=UTC),
    )
    assert not revoked_record.is_active()

    # Expired
    expired_record = ServiceTokenRecord(
        identifier="test",
        secret_hash="hash123",
        expires_at=datetime.now(tz=UTC) - timedelta(hours=1),
    )
    assert not expired_record.is_active()


# AuthTelemetry tests
def test_auth_telemetry_record_event() -> None:
    """AuthTelemetry records events and updates counters."""
    from orcheo_backend.app.authentication import AuthEvent, AuthTelemetry

    telemetry = AuthTelemetry()
    event = AuthEvent(
        event="test",
        status="success",
        subject="user-1",
        identity_type="user",
        token_id="token-1",
    )

    telemetry.record(event)

    assert len(telemetry.events()) == 1
    assert telemetry.metrics()["test:success"] == 1


def test_auth_telemetry_record_auth_success() -> None:
    """record_auth_success creates a success event."""
    from orcheo_backend.app.authentication import AuthTelemetry

    telemetry = AuthTelemetry()
    context = RequestContext(subject="user-1", identity_type="user")

    telemetry.record_auth_success(context, ip="1.2.3.4")

    events = telemetry.events()
    assert len(events) == 1
    assert events[0].event == "authenticate"
    assert events[0].status == "success"
    assert events[0].ip == "1.2.3.4"


def test_auth_telemetry_record_auth_failure() -> None:
    """record_auth_failure creates a failure event."""
    from orcheo_backend.app.authentication import AuthTelemetry

    telemetry = AuthTelemetry()

    telemetry.record_auth_failure(reason="invalid_token", ip="1.2.3.4")

    events = telemetry.events()
    assert len(events) == 1
    assert events[0].event == "authenticate"
    assert events[0].status == "failure"
    assert events[0].detail == "invalid_token"


def test_auth_telemetry_record_service_token_event() -> None:
    """record_service_token_event records lifecycle events."""
    from orcheo_backend.app.authentication import AuthTelemetry, ServiceTokenRecord

    telemetry = AuthTelemetry()
    record = ServiceTokenRecord(identifier="token-1", secret_hash="hash123")

    telemetry.record_service_token_event("mint", record)

    events = telemetry.events()
    assert len(events) == 1
    assert events[0].event == "service_token.mint"


def test_auth_telemetry_reset() -> None:
    """reset() clears events and counters."""
    from orcheo_backend.app.authentication import AuthEvent, AuthTelemetry

    telemetry = AuthTelemetry()
    event = AuthEvent(
        event="test",
        status="success",
        subject="user-1",
        identity_type="user",
        token_id="token-1",
    )
    telemetry.record(event)

    telemetry.reset()

    assert len(telemetry.events()) == 0
    assert len(telemetry.metrics()) == 0


# AuthSettings tests
def test_auth_settings_enforce_disabled_mode() -> None:
    """AuthSettings.enforce returns False when mode is disabled."""
    from orcheo_backend.app.authentication import AuthSettings

    settings = AuthSettings(
        mode="disabled",
        jwt_secret=None,
        jwks_url=None,
        jwks_static=(),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=(),
        audiences=(),
        issuer=None,
        service_token_db_path=None,
        bootstrap_service_token=None,
        bootstrap_token_scopes=frozenset(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    assert not settings.enforce


def test_auth_settings_enforce_required_mode() -> None:
    """AuthSettings.enforce returns True when mode is required."""
    from orcheo_backend.app.authentication import AuthSettings

    settings = AuthSettings(
        mode="required",
        jwt_secret=None,
        jwks_url=None,
        jwks_static=(),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=(),
        audiences=(),
        issuer=None,
        service_token_db_path=None,
        bootstrap_service_token=None,
        bootstrap_token_scopes=frozenset(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    assert settings.enforce


def test_auth_settings_enforce_optional_with_credentials() -> None:
    """AuthSettings.enforce returns True when optional mode has credentials."""
    from orcheo_backend.app.authentication import AuthSettings

    settings = AuthSettings(
        mode="optional",
        jwt_secret="secret",
        jwks_url=None,
        jwks_static=(),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=(),
        audiences=(),
        issuer=None,
        service_token_db_path=None,
        bootstrap_service_token=None,
        bootstrap_token_scopes=frozenset(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    assert settings.enforce


# SlidingWindowRateLimiter tests
def test_sliding_window_rate_limiter_disabled_when_limit_zero() -> None:
    """Rate limiter does not enforce when limit is 0."""
    from orcheo_backend.app.authentication import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter(
        0, 60, code="test", message_template="Test {key}"
    )

    # Should not raise
    for _ in range(100):
        limiter.hit("test-key")


def test_sliding_window_rate_limiter_ignores_empty_key() -> None:
    """Rate limiter does not enforce when key is empty."""
    from orcheo_backend.app.authentication import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter(
        5, 60, code="test", message_template="Test {key}"
    )

    # Should not raise
    for _ in range(100):
        limiter.hit("")


def test_sliding_window_rate_limiter_reset() -> None:
    """reset() clears internal state."""
    from orcheo_backend.app.authentication import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter(
        2, 60, code="test", message_template="Test {key}"
    )

    limiter.hit("test-key")
    limiter.hit("test-key")

    limiter.reset()

    # Should not raise after reset
    limiter.hit("test-key")
    limiter.hit("test-key")


def test_auth_rate_limiter_check_ip_and_identity() -> None:
    """AuthRateLimiter checks both IP and identity limits."""
    from orcheo_backend.app.authentication import AuthRateLimiter

    limiter = AuthRateLimiter(ip_limit=2, identity_limit=2, interval_seconds=60)

    # IP limiting
    limiter.check_ip("1.2.3.4")
    limiter.check_ip("1.2.3.4")

    with pytest.raises(AuthenticationError) as exc:
        limiter.check_ip("1.2.3.4")
    assert exc.value.code == "auth.rate_limited.ip"

    # Identity limiting
    limiter.reset()
    limiter.check_identity("user-1")
    limiter.check_identity("user-1")

    with pytest.raises(AuthenticationError) as exc:
        limiter.check_identity("user-1")
    assert exc.value.code == "auth.rate_limited.identity"


# AuthenticationError tests
def test_authentication_error_as_http_exception() -> None:
    """as_http_exception converts to HTTPException."""

    error = AuthenticationError(
        "Test error",
        code="test.error",
        status_code=401,
    )

    exception = error.as_http_exception()

    assert exception.status_code == 401
    assert exception.detail["code"] == "test.error"
    assert exception.detail["message"] == "Test error"
    assert "WWW-Authenticate" in exception.headers


def test_authorization_error_defaults() -> None:
    """AuthorizationError has correct default values when instantiated properly."""

    # AuthorizationError is a dataclass with field defaults that need to be set properly
    error = AuthorizationError(
        message="Forbidden",
        code="auth.forbidden",
        status_code=403,
        websocket_code=4403,
    )

    assert error.status_code == 403
    assert error.websocket_code == 4403
    assert error.code == "auth.forbidden"


# ServiceTokenManager advanced tests
@pytest.mark.asyncio
async def test_service_token_manager_authenticate_revoked_token() -> None:
    """Authenticate raises when token is revoked."""

    token = "revoked-token"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()

    record = ServiceTokenRecord(
        identifier="revoked",
        secret_hash=digest,
        revoked_at=datetime.now(tz=UTC),
    )
    repository = InMemoryServiceTokenRepository()
    await repository.create(record)
    manager = ServiceTokenManager(repository)

    with pytest.raises(AuthenticationError) as exc:
        await manager.authenticate(token)
    assert exc.value.code == "auth.token_revoked"
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_service_token_manager_authenticate_expired_token() -> None:
    """Authenticate raises when token is expired."""

    token = "expired-token"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()

    record = ServiceTokenRecord(
        identifier="expired",
        secret_hash=digest,
        expires_at=datetime.now(tz=UTC) - timedelta(hours=1),
    )
    repository = InMemoryServiceTokenRepository()
    await repository.create(record)
    manager = ServiceTokenManager(repository)

    with pytest.raises(AuthenticationError) as exc:
        await manager.authenticate(token)
    assert exc.value.code == "auth.token_expired"
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_service_token_manager_mint_with_timedelta() -> None:
    """Mint can accept timedelta for expires_in."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)
    secret, record = await manager.mint(expires_in=timedelta(hours=1))

    assert record.matches(secret)
    assert record.expires_at is not None


@pytest.mark.asyncio
async def test_service_token_manager_mint_with_seconds() -> None:
    """Mint can accept int seconds for expires_in."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)
    secret, record = await manager.mint(expires_in=3600)

    assert record.matches(secret)
    assert record.expires_at is not None


@pytest.mark.asyncio
async def test_service_token_manager_mint_without_expiry() -> None:
    """Mint creates token without expiry when expires_in is None."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)
    secret, record = await manager.mint()

    assert record.matches(secret)
    assert record.expires_at is None


@pytest.mark.asyncio
async def test_service_token_manager_rotate_with_overlap() -> None:
    """Rotate allows overlap period before old token expires."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)
    original_secret, original_record = await manager.mint()

    new_secret, new_record = await manager.rotate(
        original_record.identifier,
        overlap_seconds=300,
    )

    # Both tokens should work during overlap
    authenticated_original = await manager.authenticate(original_secret)
    assert authenticated_original.identifier == original_record.identifier
    authenticated_new = await manager.authenticate(new_secret)
    assert authenticated_new.identifier == new_record.identifier


@pytest.mark.asyncio
async def test_service_token_manager_rotate_without_overlap() -> None:
    """Rotate with overlap_seconds=0 expires old token immediately."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)
    original_secret, original_record = await manager.mint()

    new_secret, new_record = await manager.rotate(
        original_record.identifier,
        overlap_seconds=0,
    )

    # New token should work
    authenticated = await manager.authenticate(new_secret)
    assert authenticated.identifier == new_record.identifier


@pytest.mark.asyncio
async def test_service_token_manager_rotate_nonexistent_raises() -> None:
    """Rotate raises KeyError for nonexistent identifier."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)

    with pytest.raises(KeyError):
        await manager.rotate("nonexistent")


@pytest.mark.asyncio
async def test_service_token_manager_revoke_nonexistent_raises() -> None:
    """Revoke raises KeyError for nonexistent identifier."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)

    with pytest.raises(KeyError):
        await manager.revoke("nonexistent", reason="test")


@pytest.mark.asyncio
async def test_service_token_manager_all() -> None:
    """all() returns all managed tokens."""

    record1 = ServiceTokenRecord(identifier="token-1", secret_hash="hash1")
    record2 = ServiceTokenRecord(identifier="token-2", secret_hash="hash2")
    repository = InMemoryServiceTokenRepository()
    await repository.create(record1)
    await repository.create(record2)
    manager = ServiceTokenManager(repository)

    all_tokens = await manager.all()

    assert len(all_tokens) == 2
    identifiers = {token.identifier for token in all_tokens}
    assert "token-1" in identifiers
    assert "token-2" in identifiers


# JWT authentication tests
def test_jwt_with_audience_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT with correct audience is accepted."""

    secret = "jwt-secret"
    monkeypatch.setenv("ORCHEO_AUTH_JWT_SECRET", secret)
    monkeypatch.setenv("ORCHEO_AUTH_AUDIENCE", "orcheo-api")
    reset_authentication_state()

    now = datetime.now(tz=UTC)
    token = jwt.encode(
        {
            "sub": "tester",
            "aud": "orcheo-api",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )

    client = _client()
    response = client.get(
        "/api/workflows",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


def test_jwt_with_invalid_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT with wrong audience is rejected."""

    secret = "jwt-secret"
    monkeypatch.setenv("ORCHEO_AUTH_JWT_SECRET", secret)
    monkeypatch.setenv("ORCHEO_AUTH_AUDIENCE", "orcheo-api")
    reset_authentication_state()

    now = datetime.now(tz=UTC)
    token = jwt.encode(
        {
            "sub": "tester",
            "aud": "wrong-audience",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )

    client = _client()
    response = client.get(
        "/api/workflows",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "auth.invalid_audience"


def test_jwt_with_issuer_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT with correct issuer is accepted."""

    secret = "jwt-secret"
    monkeypatch.setenv("ORCHEO_AUTH_JWT_SECRET", secret)
    monkeypatch.setenv("ORCHEO_AUTH_ISSUER", "https://auth.orcheo.com")
    reset_authentication_state()

    now = datetime.now(tz=UTC)
    token = jwt.encode(
        {
            "sub": "tester",
            "iss": "https://auth.orcheo.com",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )

    client = _client()
    response = client.get(
        "/api/workflows",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


def test_jwt_with_invalid_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT with wrong issuer is rejected."""

    secret = "jwt-secret"
    monkeypatch.setenv("ORCHEO_AUTH_JWT_SECRET", secret)
    monkeypatch.setenv("ORCHEO_AUTH_ISSUER", "https://auth.orcheo.com")
    reset_authentication_state()

    now = datetime.now(tz=UTC)
    token = jwt.encode(
        {
            "sub": "tester",
            "iss": "https://evil.com",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )

    client = _client()
    response = client.get(
        "/api/workflows",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "auth.invalid_issuer"


def test_jwt_expired_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expired JWT is rejected."""

    secret = "jwt-secret"
    monkeypatch.setenv("ORCHEO_AUTH_JWT_SECRET", secret)
    reset_authentication_state()

    now = datetime.now(tz=UTC)
    token = jwt.encode(
        {
            "sub": "tester",
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(hours=1)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )

    client = _client()
    response = client.get(
        "/api/workflows",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "auth.token_expired"


def test_jwt_with_unsupported_algorithm(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT with unsupported algorithm is rejected."""

    secret = "jwt-secret"
    monkeypatch.setenv("ORCHEO_AUTH_JWT_SECRET", secret)
    monkeypatch.setenv("ORCHEO_AUTH_ALLOWED_ALGORITHMS", "HS256")
    reset_authentication_state()

    now = datetime.now(tz=UTC)
    token = jwt.encode(
        {
            "sub": "tester",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        secret,
        algorithm="HS384",
    )

    client = _client()
    response = client.get(
        "/api/workflows",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "auth.unsupported_algorithm"


# Bootstrap service token tests
def test_bootstrap_token_allows_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bootstrap service token from environment authenticates requests."""
    bootstrap_token = "bootstrap-secret-token"
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN", bootstrap_token)
    monkeypatch.setenv("ORCHEO_AUTH_MODE", "required")
    reset_authentication_state()

    client = _client()
    response = client.get(
        "/api/workflows",
        headers={"Authorization": f"Bearer {bootstrap_token}"},
    )

    assert response.status_code == 200


def test_bootstrap_token_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid bootstrap token is rejected."""
    bootstrap_token = "bootstrap-secret-token"
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN", bootstrap_token)
    monkeypatch.setenv("ORCHEO_AUTH_MODE", "required")
    reset_authentication_state()

    client = _client()
    response = client.get(
        "/api/workflows",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "auth.invalid_token"


def test_bootstrap_token_grants_default_admin_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bootstrap token has default admin scopes."""
    from orcheo_backend.app.authentication import get_authenticator

    bootstrap_token = "bootstrap-secret-token"
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN", bootstrap_token)
    reset_authentication_state()

    authenticator = get_authenticator()
    context = None

    async def _authenticate() -> None:
        nonlocal context
        context = await authenticator.authenticate(bootstrap_token)

    import asyncio

    asyncio.run(_authenticate())

    assert context is not None
    assert context.subject == "bootstrap"
    assert context.identity_type == "service"
    assert context.token_id == "bootstrap"
    assert "admin:tokens:read" in context.scopes
    assert "admin:tokens:write" in context.scopes
    assert "workflows:read" in context.scopes
    assert "workflows:write" in context.scopes
    assert "workflows:execute" in context.scopes
    assert "vault:read" in context.scopes
    assert "vault:write" in context.scopes


def test_bootstrap_token_respects_custom_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bootstrap token can have custom scopes configured."""
    from orcheo_backend.app.authentication import get_authenticator

    bootstrap_token = "bootstrap-secret-token"
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN", bootstrap_token)
    monkeypatch.setenv(
        "ORCHEO_AUTH_BOOTSTRAP_TOKEN_SCOPES", "workflows:read,workflows:write"
    )
    reset_authentication_state()

    authenticator = get_authenticator()
    context = None

    async def _authenticate() -> None:
        nonlocal context
        context = await authenticator.authenticate(bootstrap_token)

    import asyncio

    asyncio.run(_authenticate())

    assert context is not None
    assert context.scopes == frozenset(["workflows:read", "workflows:write"])
    assert "admin:tokens:write" not in context.scopes


def test_bootstrap_token_has_no_workspace_restrictions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bootstrap token has no workspace restrictions."""
    from orcheo_backend.app.authentication import get_authenticator

    bootstrap_token = "bootstrap-secret-token"
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN", bootstrap_token)
    reset_authentication_state()

    authenticator = get_authenticator()
    context = None

    async def _authenticate() -> None:
        nonlocal context
        context = await authenticator.authenticate(bootstrap_token)

    import asyncio

    asyncio.run(_authenticate())

    assert context is not None
    assert context.workspace_ids == frozenset()


def test_bootstrap_token_defaults_to_no_expiration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bootstrap token does not expire when no expiry is configured."""
    from orcheo_backend.app.authentication import get_authenticator

    bootstrap_token = "bootstrap-secret-token"
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN", bootstrap_token)
    reset_authentication_state()

    authenticator = get_authenticator()
    context = None

    async def _authenticate() -> None:
        nonlocal context
        context = await authenticator.authenticate(bootstrap_token)

    import asyncio

    asyncio.run(_authenticate())

    assert context is not None
    assert context.expires_at is None
    assert context.issued_at is None


def test_bootstrap_token_honours_future_expiration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bootstrap token returns configured expiry when still valid."""
    from orcheo_backend.app.authentication import get_authenticator

    bootstrap_token = "bootstrap-secret-token"
    expires_at = datetime.now(tz=UTC) + timedelta(minutes=10)
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN", bootstrap_token)
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_TOKEN_EXPIRES_AT", expires_at.isoformat())
    reset_authentication_state()

    authenticator = get_authenticator()
    context = None

    async def _authenticate() -> None:
        nonlocal context
        context = await authenticator.authenticate(bootstrap_token)

    import asyncio

    asyncio.run(_authenticate())

    assert context is not None
    assert context.expires_at == expires_at
    assert context.claims.get("expires_at") == expires_at.isoformat()


def test_bootstrap_token_is_rejected_when_expired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expired bootstrap token produces an authentication error."""
    bootstrap_token = "bootstrap-secret-token"
    expires_at = datetime.now(tz=UTC) - timedelta(minutes=1)
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN", bootstrap_token)
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_TOKEN_EXPIRES_AT", expires_at.isoformat())
    monkeypatch.setenv("ORCHEO_AUTH_MODE", "required")
    reset_authentication_state()

    client = _client()
    response = client.get(
        "/api/workflows",
        headers={"Authorization": f"Bearer {bootstrap_token}"},
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "auth.token_expired"
    assert "expired" in detail["message"]


def test_bootstrap_token_logs_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bootstrap token usage is logged to telemetry."""
    bootstrap_token = "bootstrap-secret-token"
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN", bootstrap_token)
    monkeypatch.setenv("ORCHEO_AUTH_MODE", "required")
    reset_authentication_state()

    client = _client()
    response = client.get(
        "/api/workflows",
        headers={"Authorization": f"Bearer {bootstrap_token}"},
    )

    assert response.status_code == 200

    # Check telemetry recorded the bootstrap token usage
    events = auth_telemetry.events()
    bootstrap_events = [e for e in events if e.identity_type == "bootstrap_service"]
    assert len(bootstrap_events) >= 1
    assert bootstrap_events[0].status == "success"
    assert bootstrap_events[0].subject == "bootstrap"
    assert bootstrap_events[0].token_id == "bootstrap"


def test_bootstrap_token_with_database_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bootstrap token works alongside database-persisted tokens."""
    # Set up both bootstrap token and database token
    bootstrap_token = "bootstrap-secret-token"
    db_token = "database-token"

    _setup_service_token(
        monkeypatch,
        db_token,
        identifier="db-token",
        scopes=["workflows:read"],
    )
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN", bootstrap_token)
    reset_authentication_state()

    client = _client()

    # Test bootstrap token works
    response1 = client.get(
        "/api/workflows",
        headers={"Authorization": f"Bearer {bootstrap_token}"},
    )
    assert response1.status_code == 200

    # Test database token works
    response2 = client.get(
        "/api/workflows",
        headers={"Authorization": f"Bearer {db_token}"},
    )
    assert response2.status_code == 200


def test_bootstrap_token_enforces_authentication_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bootstrap token enables enforce mode when AUTH_MODE is optional."""
    bootstrap_token = "bootstrap-secret-token"
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN", bootstrap_token)
    monkeypatch.setenv("ORCHEO_AUTH_MODE", "optional")
    reset_authentication_state()

    settings = load_auth_settings()
    assert settings.enforce is True
    assert settings.bootstrap_service_token == bootstrap_token


def test_load_auth_settings_includes_bootstrap_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """load_auth_settings correctly parses bootstrap token configuration."""
    bootstrap_token = "my-bootstrap-token"
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN", bootstrap_token)
    monkeypatch.setenv(
        "ORCHEO_AUTH_BOOTSTRAP_TOKEN_SCOPES", "workflows:read,vault:write"
    )
    reset_authentication_state()

    settings = load_auth_settings()
    assert settings.bootstrap_service_token == bootstrap_token
    assert settings.bootstrap_token_scopes == frozenset(
        ["workflows:read", "vault:write"]
    )
    assert settings.bootstrap_token_expires_at is None


def test_load_auth_settings_parses_bootstrap_token_expiration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bootstrap token expiration is parsed into an aware datetime."""
    bootstrap_token = "my-bootstrap-token"
    expires_at = datetime.now(tz=UTC) + timedelta(hours=1)
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN", bootstrap_token)
    monkeypatch.setenv("ORCHEO_AUTH_BOOTSTRAP_TOKEN_EXPIRES_AT", expires_at.isoformat())
    reset_authentication_state()

    settings = load_auth_settings()
    assert settings.bootstrap_service_token == bootstrap_token
    assert settings.bootstrap_token_expires_at == expires_at


def test_parse_timestamp_with_naive_datetime() -> None:
    """_parse_timestamp converts naive datetime to aware datetime."""
    from orcheo_backend.app.authentication import _parse_timestamp

    # Test with naive datetime (no timezone info)
    naive_dt = datetime(2024, 11, 4, 12, 0, 0)
    result = _parse_timestamp(naive_dt)

    assert result is not None
    assert result.tzinfo == UTC
    assert result.year == 2024
    assert result.month == 11
    assert result.day == 4
    assert result.hour == 12
    assert result.minute == 0
    assert result.second == 0
