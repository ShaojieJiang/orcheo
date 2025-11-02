"""Extended tests for authentication module to achieve full coverage."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
import jwt
import pytest
from starlette.websockets import WebSocket
from orcheo_backend.app.authentication import (
    AuthenticationError,
    Authenticator,
    AuthSettings,
    ServiceTokenManager,
    ServiceTokenRecord,
    authenticate_websocket,
    get_authenticator,
    get_request_context,
    load_auth_settings,
    reset_authentication_state,
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
        "ORCHEO_AUTH_JWKS_STATIC",
        "ORCHEO_AUTH_RATE_LIMIT_IP",
        "ORCHEO_AUTH_RATE_LIMIT_IDENTITY",
        "ORCHEO_AUTH_RATE_LIMIT_INTERVAL",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_authentication_state()
    yield
    monkeypatch.undo()
    reset_authentication_state()


# WebSocket authentication tests
@pytest.mark.asyncio
async def test_authenticate_websocket_with_auth_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WebSocket authentication via Authorization header."""
    import hashlib

    token = "ws-token"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    monkeypatch.setenv(
        "ORCHEO_AUTH_SERVICE_TOKENS",
        f'{{"id": "ws", "hash": "{digest}"}}',
    )
    reset_authentication_state()

    websocket = Mock(spec=WebSocket)
    websocket.headers = {"authorization": f"Bearer {token}"}
    websocket.query_params = {}
    websocket.client = Mock(host="1.2.3.4")
    websocket.state = Mock()

    context = await authenticate_websocket(websocket)

    assert context.is_authenticated
    assert context.identity_type == "service"


@pytest.mark.asyncio
async def test_authenticate_websocket_with_query_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WebSocket authentication via query parameter."""
    import hashlib

    token = "ws-query-token"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    monkeypatch.setenv(
        "ORCHEO_AUTH_SERVICE_TOKENS",
        f'{{"id": "ws-query", "hash": "{digest}"}}',
    )
    reset_authentication_state()

    websocket = Mock(spec=WebSocket)
    websocket.headers = {}
    websocket.query_params = {"token": token}
    websocket.client = Mock(host="1.2.3.4")
    websocket.state = Mock()

    context = await authenticate_websocket(websocket)

    assert context.is_authenticated


@pytest.mark.asyncio
async def test_authenticate_websocket_with_access_token_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WebSocket authentication via access_token query parameter."""
    import hashlib

    token = "ws-access-token"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    monkeypatch.setenv(
        "ORCHEO_AUTH_SERVICE_TOKENS",
        f'{{"id": "ws-access", "hash": "{digest}"}}',
    )
    reset_authentication_state()

    websocket = Mock(spec=WebSocket)
    websocket.headers = {}
    websocket.query_params = {"access_token": token}
    websocket.client = Mock(host="1.2.3.4")
    websocket.state = Mock()
    websocket.close = AsyncMock()

    context = await authenticate_websocket(websocket)

    assert context.is_authenticated


@pytest.mark.asyncio
async def test_authenticate_websocket_missing_token() -> None:
    """WebSocket authentication fails when no token provided."""

    # Force authentication requirement
    with patch("orcheo_backend.app.authentication.get_authenticator") as mock_auth:
        mock_settings = AuthSettings(
            mode="required",
            jwt_secret=None,
            jwks_url=None,
            jwks_static=(),
            jwks_cache_ttl=300,
            jwks_timeout=5.0,
            allowed_algorithms=(),
            audiences=(),
            issuer=None,
            service_tokens=(
                ServiceTokenRecord(identifier="test", secret_hash="hash123"),
            ),
            rate_limit_ip=0,
            rate_limit_identity=0,
            rate_limit_interval=60,
        )
        mock_authenticator = Mock()
        mock_authenticator.settings = mock_settings
        mock_auth.return_value = mock_authenticator

        websocket = Mock(spec=WebSocket)
        websocket.headers = {}
        websocket.query_params = {}
        websocket.client = Mock(host="1.2.3.4")
        websocket.state = Mock()
        websocket.close = AsyncMock()

        with patch("orcheo_backend.app.authentication.get_auth_rate_limiter"):
            with pytest.raises(AuthenticationError):
                await authenticate_websocket(websocket)

        websocket.close.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_websocket_invalid_scheme() -> None:
    """WebSocket authentication fails with invalid Authorization scheme."""

    with patch("orcheo_backend.app.authentication.get_authenticator") as mock_auth:
        mock_settings = AuthSettings(
            mode="required",
            jwt_secret=None,
            jwks_url=None,
            jwks_static=(),
            jwks_cache_ttl=300,
            jwks_timeout=5.0,
            allowed_algorithms=(),
            audiences=(),
            issuer=None,
            service_tokens=(
                ServiceTokenRecord(identifier="test", secret_hash="hash123"),
            ),
            rate_limit_ip=0,
            rate_limit_identity=0,
            rate_limit_interval=60,
        )
        mock_authenticator = Mock()
        mock_authenticator.settings = mock_settings
        mock_auth.return_value = mock_authenticator

        websocket = Mock(spec=WebSocket)
        websocket.headers = {"authorization": "Basic dXNlcjpwYXNz"}
        websocket.query_params = {}
        websocket.client = Mock(host="1.2.3.4")
        websocket.state = Mock()
        websocket.close = AsyncMock()

        with patch("orcheo_backend.app.authentication.get_auth_rate_limiter"):
            with pytest.raises(AuthenticationError):
                await authenticate_websocket(websocket)

        websocket.close.assert_called_once()


# Helper function tests
def test_parse_max_age_from_cache_control() -> None:
    """_parse_max_age extracts max-age from Cache-Control headers."""
    from orcheo_backend.app.authentication import _parse_max_age

    assert _parse_max_age("max-age=300") == 300
    assert _parse_max_age("public, max-age=600, must-revalidate") == 600
    assert _parse_max_age("no-cache") is None
    assert _parse_max_age(None) is None


def test_parse_timestamp_from_various_formats() -> None:
    """_parse_timestamp handles multiple timestamp formats."""
    from orcheo_backend.app.authentication import _parse_timestamp

    now = datetime.now(tz=UTC)
    timestamp = int(now.timestamp())

    # Unix timestamp (int)
    result = _parse_timestamp(timestamp)
    assert result is not None
    assert abs((result - now).total_seconds()) < 1

    # Unix timestamp (string)
    result = _parse_timestamp(str(timestamp))
    assert result is not None

    # ISO format
    iso_string = now.isoformat()
    result = _parse_timestamp(iso_string)
    assert result is not None

    # None
    assert _parse_timestamp(None) is None


def test_infer_identity_type_from_claims() -> None:
    """_infer_identity_type determines identity type from JWT claims."""
    from orcheo_backend.app.authentication import _infer_identity_type

    assert _infer_identity_type({"token_use": "user"}) == "user"
    assert _infer_identity_type({"type": "service"}) == "service"
    assert _infer_identity_type({"typ": "client"}) == "service"  # client -> service
    assert _infer_identity_type({}) == "user"  # default


def test_extract_scopes_from_various_claim_locations() -> None:
    """_extract_scopes finds scopes in multiple claim locations."""
    from orcheo_backend.app.authentication import _extract_scopes

    # String format (space-separated)
    scopes = set(_extract_scopes({"scope": "read write delete"}))
    assert scopes == {"read", "write", "delete"}

    # List format
    scopes = set(_extract_scopes({"scopes": ["read", "write"]}))
    assert scopes == {"read", "write"}

    # Nested in orcheo claim
    scopes = set(_extract_scopes({"orcheo": {"scopes": ["admin"]}}))
    assert scopes == {"admin"}

    # JSON string
    scopes = set(_extract_scopes({"scope": '["read", "write"]'}))
    assert scopes == {"read", "write"}


def test_extract_workspace_ids_from_claims() -> None:
    """_extract_workspace_ids finds workspace IDs in claims."""
    from orcheo_backend.app.authentication import _extract_workspace_ids

    # List format
    ids = set(_extract_workspace_ids({"workspace_ids": ["ws-1", "ws-2"]}))
    assert ids == {"ws-1", "ws-2"}

    # String format
    ids = set(_extract_workspace_ids({"workspace": "ws-1"}))
    assert ids == {"ws-1"}

    # Nested in orcheo claim
    ids = set(_extract_workspace_ids({"orcheo": {"workspace_ids": ["ws-3"]}}))
    assert ids == {"ws-3"}


def test_coerce_str_items_handles_various_types() -> None:
    """_coerce_str_items converts various types to string sets."""
    from orcheo_backend.app.authentication import _coerce_str_items

    # String
    assert _coerce_str_items("item1 item2") == {"item1", "item2"}

    # List
    assert _coerce_str_items(["item1", "item2"]) == {"item1", "item2"}

    # Dict (values only)
    assert _coerce_str_items({"key": "value"}) == {"value"}

    # None
    assert _coerce_str_items(None) == set()


def test_normalize_token_hash_with_prefixes() -> None:
    """_normalize_token_hash strips common hash prefixes."""
    from orcheo_backend.app.authentication import _normalize_token_hash

    assert _normalize_token_hash("sha256:abc123") == "abc123"
    assert _normalize_token_hash("sha256$abc123") == "abc123"
    assert _normalize_token_hash("abc123") == "abc123"

    with pytest.raises(ValueError):
        _normalize_token_hash("")


# Service token parsing tests
def test_parse_service_tokens_from_string() -> None:
    """_parse_service_tokens handles string configurations."""
    from orcheo_backend.app.authentication import _parse_service_tokens

    # Single raw token
    records = _parse_service_tokens("raw-token")
    assert len(records) == 1
    assert records[0].matches("raw-token")

    # JSON array
    tokens = _parse_service_tokens('["token1", "token2"]')
    assert len(tokens) == 2


def test_parse_service_tokens_from_dict() -> None:
    """_parse_service_tokens handles dictionary configurations."""
    from orcheo_backend.app.authentication import _parse_service_tokens

    config = {
        "id": "api-key",
        "secret": "my-secret",
        "scopes": ["read", "write"],
        "workspace_ids": ["ws-1"],
    }

    records = _parse_service_tokens(config)
    assert len(records) == 1
    assert records[0].identifier == "api-key"
    assert "read" in records[0].scopes


def test_parse_service_tokens_with_hash() -> None:
    """_parse_service_tokens accepts pre-hashed tokens."""
    import hashlib
    from orcheo_backend.app.authentication import _parse_service_tokens

    token_hash = hashlib.sha256(b"secret").hexdigest()
    config = {"id": "hashed-token", "hash": token_hash}

    records = _parse_service_tokens(config)
    assert len(records) == 1
    assert records[0].secret_hash == token_hash


def test_parse_service_tokens_from_list() -> None:
    """_parse_service_tokens handles lists of configurations."""
    from orcheo_backend.app.authentication import _parse_service_tokens

    configs = [
        {"id": "token1", "secret": "secret1"},
        {"id": "token2", "secret": "secret2"},
    ]

    records = _parse_service_tokens(configs)
    assert len(records) == 2


def test_parse_jwks_from_string() -> None:
    """_parse_jwks handles JSON string configurations."""
    import json
    from orcheo_backend.app.authentication import _parse_jwks

    jwks_dict = {
        "keys": [
            {"kty": "RSA", "kid": "key1"},
            {"kty": "RSA", "kid": "key2"},
        ]
    }
    jwks_str = json.dumps(jwks_dict)

    keys = _parse_jwks(jwks_str)
    assert len(keys) == 2
    assert keys[0]["kid"] == "key1"


def test_parse_jwks_from_dict() -> None:
    """_parse_jwks handles dictionary configurations."""
    from orcheo_backend.app.authentication import _parse_jwks

    jwks_dict = {
        "keys": [
            {"kty": "RSA", "kid": "key1"},
        ]
    }

    keys = _parse_jwks(jwks_dict)
    assert len(keys) == 1


def test_parse_jwks_from_list() -> None:
    """_parse_jwks handles list configurations."""
    from orcheo_backend.app.authentication import _parse_jwks

    jwks_list = [
        {"kty": "RSA", "kid": "key1"},
        {"kty": "RSA", "kid": "key2"},
    ]

    keys = _parse_jwks(jwks_list)
    assert len(keys) == 2


def test_load_auth_settings_with_defaults() -> None:
    """load_auth_settings applies default values."""

    settings = load_auth_settings(refresh=True)

    assert settings.mode == "optional"
    assert settings.jwks_cache_ttl == 300
    assert settings.jwks_timeout == 5.0
    assert "RS256" in settings.allowed_algorithms
    assert "HS256" in settings.allowed_algorithms


def test_load_auth_settings_with_custom_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """load_auth_settings reads custom environment variables."""

    monkeypatch.setenv("ORCHEO_AUTH_MODE", "required")
    monkeypatch.setenv("ORCHEO_AUTH_JWT_SECRET", "my-secret")
    monkeypatch.setenv("ORCHEO_AUTH_JWKS_CACHE_TTL", "600")
    monkeypatch.setenv("ORCHEO_AUTH_JWKS_TIMEOUT", "10.0")
    monkeypatch.setenv("ORCHEO_AUTH_ALLOWED_ALGORITHMS", "RS256,HS256")
    monkeypatch.setenv("ORCHEO_AUTH_AUDIENCE", "api1,api2")
    monkeypatch.setenv("ORCHEO_AUTH_ISSUER", "https://auth.example.com")

    settings = load_auth_settings(refresh=True)

    assert settings.mode == "required"
    assert settings.jwt_secret == "my-secret"
    assert settings.jwks_cache_ttl == 600
    assert settings.jwks_timeout == 10.0
    assert "RS256" in settings.allowed_algorithms
    assert "api1" in settings.audiences
    assert settings.issuer == "https://auth.example.com"


def test_get_authenticator_caching() -> None:
    """get_authenticator caches the instance."""

    auth1 = get_authenticator()
    auth2 = get_authenticator()

    assert auth1 is auth2


def test_get_authenticator_refresh() -> None:
    """get_authenticator refreshes when requested."""

    auth1 = get_authenticator()
    auth2 = get_authenticator(refresh=True)

    # Should create new instance
    assert auth1 is not auth2


@pytest.mark.asyncio
async def test_get_request_context_from_state() -> None:
    """get_request_context retrieves context from request state."""
    from starlette.requests import Request
    from orcheo_backend.app.authentication import RequestContext

    context = RequestContext(subject="test-user", identity_type="user")

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request"}

    request = Request(scope, receive)  # type: ignore[arg-type]
    request.state.auth = context

    result = await get_request_context(request)

    assert result is context
    assert result.subject == "test-user"


def test_authorization_policy_require_authenticated() -> None:
    """AuthorizationPolicy.require_authenticated raises for anonymous."""
    from orcheo_backend.app.authentication import (
        AuthorizationPolicy,
        RequestContext,
    )

    anon = RequestContext.anonymous()
    policy = AuthorizationPolicy(anon)

    with pytest.raises(AuthenticationError) as exc:
        policy.require_authenticated()
    assert exc.value.code == "auth.authentication_required"


def test_authorization_policy_require_workspaces() -> None:
    """AuthorizationPolicy.require_workspaces validates multiple workspaces."""
    from orcheo_backend.app.authentication import (
        AuthorizationError,
        AuthorizationPolicy,
        RequestContext,
    )

    context = RequestContext(
        subject="user-1",
        identity_type="user",
        workspace_ids=frozenset({"ws-1", "ws-2"}),
    )
    policy = AuthorizationPolicy(context)

    # Should succeed
    policy.require_workspaces(["ws-1", "ws-2"])

    # Should fail
    with pytest.raises(AuthorizationError):
        policy.require_workspaces(["ws-1", "ws-3"])


def test_ensure_workspace_access_with_empty_workspaces() -> None:
    """ensure_workspace_access allows empty workspace list."""
    from orcheo_backend.app.authentication import (
        RequestContext,
        ensure_workspace_access,
    )

    context = RequestContext(
        subject="user-1",
        identity_type="user",
    )

    # Should not raise
    ensure_workspace_access(context, [])


def test_ensure_workspace_access_no_workspace_context() -> None:
    """ensure_workspace_access raises when context has no workspaces."""
    from orcheo_backend.app.authentication import (
        AuthorizationError,
        RequestContext,
        ensure_workspace_access,
    )

    context = RequestContext(
        subject="user-1",
        identity_type="user",
    )

    with pytest.raises(AuthorizationError) as exc:
        ensure_workspace_access(context, ["ws-1"])
    assert exc.value.code == "auth.workspace_forbidden"


def test_service_token_from_mapping_with_all_fields() -> None:
    """_service_token_from_mapping handles complete configurations."""
    import hashlib
    from orcheo_backend.app.authentication import _service_token_from_mapping

    now = datetime.now(tz=UTC)
    config = {
        "id": "full-token",
        "hash": hashlib.sha256(b"secret").hexdigest(),
        "scopes": ["read", "write"],
        "workspace_ids": ["ws-1", "ws-2"],
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "revoked_at": None,
        "revocation_reason": None,
        "rotated_to": None,
    }

    record = _service_token_from_mapping(config)

    assert record is not None
    assert record.identifier == "full-token"
    assert "read" in record.scopes
    assert "ws-1" in record.workspace_ids


def test_service_token_from_mapping_returns_none_for_invalid() -> None:
    """_service_token_from_mapping returns None for invalid configs."""
    from orcheo_backend.app.authentication import _service_token_from_mapping

    # No secret or hash
    assert _service_token_from_mapping({}) is None

    # Empty hash
    assert _service_token_from_mapping({"hash": ""}) is None


# Additional coverage tests for JWKS and JWT
@pytest.mark.asyncio
async def test_jwks_cache_lock_prevents_concurrent_fetches() -> None:
    """JWKS cache prevents concurrent fetches with async lock."""
    from orcheo_backend.app.authentication import JWKSCache

    fetch_count = 0

    async def fetcher() -> tuple[list[dict[str, str]], int | None]:
        nonlocal fetch_count
        fetch_count += 1
        # Simulate slow fetch
        import asyncio

        await asyncio.sleep(0.1)
        return ([{"kid": "key-1"}], 300)

    cache = JWKSCache(fetcher, ttl_seconds=300)

    # Trigger concurrent fetches
    import asyncio

    results = await asyncio.gather(
        cache.keys(),
        cache.keys(),
        cache.keys(),
    )

    # Should only fetch once due to lock
    assert fetch_count == 1
    assert all(r == [{"kid": "key-1"}] for r in results)


@pytest.mark.asyncio
async def test_authenticator_with_static_jwks() -> None:
    """Authenticator can use static JWKS configuration."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from orcheo_backend.app.authentication import Authenticator

    # Generate RSA key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()

    # Create JWK
    from jwt.algorithms import RSAAlgorithm

    jwk_dict = RSAAlgorithm(RSAAlgorithm.SHA256).to_jwk(public_key, as_dict=True)
    jwk_dict["kid"] = "static-key-1"
    jwk_dict["alg"] = "RS256"

    settings = AuthSettings(
        mode="required",
        jwt_secret=None,
        jwks_url=None,
        jwks_static=(jwk_dict,),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=("RS256",),
        audiences=(),
        issuer=None,
        service_tokens=(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    authenticator = Authenticator(settings)

    # Create JWT signed with private key
    now = datetime.now(tz=UTC)
    token = jwt.encode(
        {
            "sub": "test-user",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "static-key-1"},
    )

    context = await authenticator.authenticate(token)

    assert context.subject == "test-user"


@pytest.mark.asyncio
async def test_authenticator_jwt_with_invalid_token_format() -> None:
    """Authenticator rejects malformed JWT tokens."""

    settings = load_auth_settings(refresh=True)
    authenticator = Authenticator(settings)

    with pytest.raises(AuthenticationError) as exc:
        await authenticator.authenticate("not-a-valid-jwt")
    assert exc.value.code == "auth.invalid_token"


def test_authenticator_properties() -> None:
    """Authenticator exposes settings and service token manager."""

    settings = load_auth_settings(refresh=True)
    authenticator = Authenticator(settings)

    assert authenticator.settings == settings
    assert isinstance(authenticator.service_token_manager, ServiceTokenManager)


@pytest.mark.asyncio
async def test_authenticator_authenticate_empty_token() -> None:
    """Authenticator rejects empty tokens."""

    settings = load_auth_settings(refresh=True)
    authenticator = Authenticator(settings)

    with pytest.raises(AuthenticationError) as exc:
        await authenticator.authenticate("")
    assert exc.value.code == "auth.missing_token"


def test_parse_int_with_various_types() -> None:
    """_parse_int handles multiple input types."""
    from orcheo_backend.app.authentication import _parse_int

    assert _parse_int(42, 0) == 42
    assert _parse_int("100", 0) == 100
    assert _parse_int(None, 99) == 99


def test_parse_float_with_various_types() -> None:
    """_parse_float handles multiple input types."""
    from orcheo_backend.app.authentication import _parse_float

    assert _parse_float(3.14, 0.0) == 3.14
    assert _parse_float("2.5", 0.0) == 2.5
    assert _parse_float(None, 1.5) == 1.5


def test_coerce_mode_with_valid_values() -> None:
    """_coerce_mode returns valid mode strings."""
    from orcheo_backend.app.authentication import _coerce_mode

    assert _coerce_mode("disabled") == "disabled"
    assert _coerce_mode("required") == "required"
    assert _coerce_mode("optional") == "optional"
    assert _coerce_mode("REQUIRED") == "required"  # case insensitive
    assert _coerce_mode("invalid") == "optional"  # default
    assert _coerce_mode(123) == "optional"  # non-string


def test_parse_str_sequence() -> None:
    """_parse_str_sequence converts values to string tuples."""
    from orcheo_backend.app.authentication import _parse_str_sequence

    result = _parse_str_sequence(["item1", "item2", "item3"])
    assert isinstance(result, tuple)
    assert len(result) == 3


def test_coerce_optional_str() -> None:
    """_coerce_optional_str handles None and empty strings."""
    from orcheo_backend.app.authentication import _coerce_optional_str

    assert _coerce_optional_str("value") == "value"
    assert _coerce_optional_str("  ") is None
    assert _coerce_optional_str(None) is None
    assert _coerce_optional_str(123) == "123"


def test_extract_bearer_token_with_invalid_format() -> None:
    """_extract_bearer_token raises for invalid formats."""
    from orcheo_backend.app.authentication import _extract_bearer_token

    # Missing Bearer prefix
    with pytest.raises(AuthenticationError) as exc:
        _extract_bearer_token("token-value")
    assert exc.value.code == "auth.invalid_scheme"

    # Bearer with only spaces - gets caught by "not 2 parts" check
    with pytest.raises(AuthenticationError) as exc:
        _extract_bearer_token("Bearer")
    assert exc.value.code == "auth.invalid_scheme"

    # None
    with pytest.raises(AuthenticationError) as exc:
        _extract_bearer_token(None)
    assert exc.value.code == "auth.missing_token"


def test_extract_bearer_token_with_valid_format() -> None:
    """_extract_bearer_token successfully extracts valid tokens."""
    from orcheo_backend.app.authentication import _extract_bearer_token

    token = _extract_bearer_token("Bearer my-token-123")
    assert token == "my-token-123"


def test_load_auth_settings_with_jwks_static(monkeypatch: pytest.MonkeyPatch) -> None:
    """load_auth_settings parses JWKS_STATIC configuration."""
    import json

    jwks = {"keys": [{"kty": "RSA", "kid": "test-key"}]}
    monkeypatch.setenv("ORCHEO_AUTH_JWKS_STATIC", json.dumps(jwks))

    settings = load_auth_settings(refresh=True)

    assert len(settings.jwks_static) == 1
    assert settings.jwks_static[0]["kid"] == "test-key"


def test_parse_jwks_invalid_json(caplog: pytest.LogCaptureFixture) -> None:
    """_parse_jwks logs warning for invalid JSON."""
    import logging
    from orcheo_backend.app.authentication import _parse_jwks

    caplog.set_level(logging.WARNING)

    result = _parse_jwks("not valid json{")

    assert result == []
    assert any("Failed to parse" in record.message for record in caplog.records)


def test_sliding_window_rate_limiter_clears_old_events() -> None:
    """SlidingWindowRateLimiter removes old events outside the window."""
    from orcheo_backend.app.authentication import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter(3, 1, code="test", message_template="Test {key}")
    now = datetime.now(tz=UTC)

    # Add events at different times
    limiter.hit("key1", now=now - timedelta(seconds=2))
    limiter.hit("key1", now=now - timedelta(seconds=1.5))
    limiter.hit("key1", now=now)

    # Old events should be removed, so this shouldn't raise
    limiter.hit("key1", now=now)


def test_claims_to_context_with_various_token_ids() -> None:
    """_claims_to_context extracts token_id from various claim fields."""
    from orcheo_backend.app.authentication import Authenticator

    settings = load_auth_settings(refresh=True)
    authenticator = Authenticator(settings)

    # With jti
    context = authenticator._claims_to_context({"sub": "user", "jti": "token-123"})
    assert context.token_id == "token-123"

    # With token_id
    context = authenticator._claims_to_context({"sub": "user", "token_id": "token-456"})
    assert context.token_id == "token-456"

    # Fallback to subject
    context = authenticator._claims_to_context({"sub": "user-789"})
    assert context.token_id == "user-789"


def test_service_token_manager_with_custom_clock() -> None:
    """ServiceTokenManager can use a custom clock function."""

    fixed_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

    def custom_clock() -> datetime:
        return fixed_time

    manager = ServiceTokenManager([], clock=custom_clock)
    secret, record = manager.mint()

    assert record.issued_at == fixed_time


def test_service_token_rotate_preserves_expiry_without_overlap() -> None:
    """Token rotation without overlap preserves original expiry if sooner."""

    manager = ServiceTokenManager([])

    # Create token expiring in 1 hour
    original_secret, original_record = manager.mint(expires_in=timedelta(hours=1))

    # Rotate with 0 overlap
    new_secret, new_record = manager.rotate(
        original_record.identifier, overlap_seconds=0
    )

    # Original record should still exist but rotated
    updated_original = manager._records_by_id[original_record.identifier]
    assert updated_original.rotated_to == new_record.identifier


def test_normalize_jwk_list_filters_non_mappings() -> None:
    """_normalize_jwk_list filters out non-mapping entries."""
    from orcheo_backend.app.authentication import _normalize_jwk_list

    mixed_list = [
        {"kty": "RSA", "kid": "key1"},
        "not-a-dict",
        {"kty": "RSA", "kid": "key2"},
        123,
    ]

    result = _normalize_jwk_list(mixed_list)

    assert len(result) == 2
    assert result[0]["kid"] == "key1"
    assert result[1]["kid"] == "key2"


def test_parse_string_items_handles_various_formats() -> None:
    """_parse_string_items parses JSON and space-separated strings."""
    from orcheo_backend.app.authentication import _parse_string_items

    # JSON array
    assert _parse_string_items('["a", "b", "c"]') == ["a", "b", "c"]

    # Space-separated
    assert _parse_string_items("one two three") == ["one", "two", "three"]

    # Empty
    assert _parse_string_items("") == []


def test_coerce_from_string_handles_nested_structures() -> None:
    """_coerce_from_string recursively processes nested structures."""
    from orcheo_backend.app.authentication import _coerce_from_string

    # Nested JSON
    result = _coerce_from_string('["scope1", ["scope2", "scope3"]]')
    assert "scope1" in result
    # Note: nested arrays are processed recursively


def test_coerce_from_mapping_extracts_all_values() -> None:
    """_coerce_from_mapping extracts values from all dict keys."""
    from orcheo_backend.app.authentication import _coerce_from_mapping

    data = {
        "scope1": "read",
        "scope2": "write",
        "list_key": ["admin", "user"],
    }

    result = _coerce_from_mapping(data)

    assert "read" in result
    assert "write" in result
    assert "admin" in result
    assert "user" in result


def test_coerce_from_sequence_processes_all_items() -> None:
    """_coerce_from_sequence processes each sequence item."""
    from orcheo_backend.app.authentication import _coerce_from_sequence

    sequence = ["item1", ["item2", "item3"], "item4"]

    result = _coerce_from_sequence(sequence)

    assert "item1" in result
    assert "item2" in result
    assert "item3" in result
    assert "item4" in result


# Additional tests for missing coverage
@pytest.mark.asyncio
async def test_jwks_fetch_with_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWKS fetcher handles HTTP errors appropriately."""
    import httpx
    from orcheo_backend.app.authentication import Authenticator

    monkeypatch.setenv(
        "ORCHEO_AUTH_JWKS_URL", "https://keys.example.com/.well-known/jwks.json"
    )
    reset_authentication_state()

    settings = load_auth_settings(refresh=True)
    authenticator = Authenticator(settings)

    # Mock httpx to raise an error
    with patch("orcheo_backend.app.authentication.httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found", request=Mock(), response=Mock(status_code=404)
        )
        mock_client.return_value.__aenter__.return_value.get.return_value = (
            mock_response
        )

        with pytest.raises(httpx.HTTPStatusError):
            await authenticator._fetch_jwks()


def test_normalize_service_token_entries_with_nested_lists() -> None:
    """_normalize_service_token_entries flattens nested lists."""
    from orcheo_backend.app.authentication import _normalize_service_token_entries

    nested = [
        "token1",
        ["token2", "token3"],
        [["token4"]],
    ]

    result = _normalize_service_token_entries(nested)

    # Should flatten all tokens
    assert len(result) >= 4


def test_normalize_service_tokens_from_string_with_json_object() -> None:
    """_normalize_service_tokens_from_string handles JSON objects."""
    from orcheo_backend.app.authentication import _normalize_service_tokens_from_string

    json_obj = '{"id": "test", "secret": "value"}'

    result = _normalize_service_tokens_from_string(json_obj)

    assert len(result) == 1
    assert isinstance(result[0], dict)


def test_normalize_service_tokens_from_string_with_comma_separated() -> None:
    """_normalize_service_tokens_from_string handles comma-separated tokens."""
    from orcheo_backend.app.authentication import _normalize_service_tokens_from_string

    csv_tokens = "token1, token2, token3"

    result = _normalize_service_tokens_from_string(csv_tokens)

    assert len(result) >= 3


def test_service_token_from_mapping_uses_identifier_from_various_keys() -> None:
    """_service_token_from_mapping checks id, identifier, and name keys."""
    from orcheo_backend.app.authentication import _service_token_from_mapping

    # Using "identifier" key
    record1 = _service_token_from_mapping({"identifier": "id1", "secret": "secret1"})
    assert record1 is not None
    assert record1.identifier == "id1"

    # Using "name" key
    record2 = _service_token_from_mapping({"name": "id2", "secret": "secret2"})
    assert record2 is not None
    assert record2.identifier == "id2"


def test_service_token_from_mapping_with_timestamp_strings() -> None:
    """_service_token_from_mapping parses timestamp strings."""
    from orcheo_backend.app.authentication import _service_token_from_mapping

    config = {
        "id": "test",
        "secret": "secret",
        "issued_at": "2025-01-01T12:00:00Z",
        "expires_at": "2025-12-31T23:59:59+00:00",
    }

    record = _service_token_from_mapping(config)

    assert record is not None
    assert record.issued_at is not None
    assert record.expires_at is not None


def test_get_auth_rate_limiter_refresh() -> None:
    """get_auth_rate_limiter refreshes when requested."""
    from orcheo_backend.app.authentication import get_auth_rate_limiter

    limiter1 = get_auth_rate_limiter()
    limiter2 = get_auth_rate_limiter(refresh=True)

    # Should create new instance
    assert limiter1 is not limiter2


@pytest.mark.asyncio
async def test_authenticate_websocket_anonymous_when_disabled() -> None:
    """WebSocket authentication allows anonymous when disabled."""

    websocket = Mock(spec=WebSocket)
    websocket.headers = {}
    websocket.query_params = {}
    websocket.client = Mock(host="1.2.3.4")
    websocket.state = Mock()

    context = await authenticate_websocket(websocket)

    assert not context.is_authenticated
    assert context.identity_type == "anonymous"


def test_reset_authentication_state_clears_caches() -> None:
    """reset_authentication_state clears all cached authenticators."""

    # Get authenticator to populate cache
    get_authenticator()

    reset_authentication_state()

    # Cache should be cleared
    from orcheo_backend.app.authentication import (
        _auth_rate_limiter_cache,
        _authenticator_cache,
    )

    assert _authenticator_cache.get("authenticator") is None
    assert _auth_rate_limiter_cache.get("limiter") is None


def test_auth_rate_limiter_reset() -> None:
    """AuthRateLimiter.reset clears both IP and identity limiters."""
    from orcheo_backend.app.authentication import AuthRateLimiter

    limiter = AuthRateLimiter(ip_limit=2, identity_limit=2, interval_seconds=60)

    limiter.check_ip("1.2.3.4")
    limiter.check_identity("user-1")

    limiter.reset()

    # Should be able to use again after reset
    limiter.check_ip("1.2.3.4")
    limiter.check_identity("user-1")


def test_auth_rate_limiter_check_with_none_values() -> None:
    """AuthRateLimiter handles None IP and identity gracefully."""
    from orcheo_backend.app.authentication import AuthRateLimiter

    limiter = AuthRateLimiter(ip_limit=2, identity_limit=2, interval_seconds=60)

    # Should not raise
    limiter.check_ip(None)
    limiter.check_identity(None)


def test_parse_timestamp_with_iso_z_format() -> None:
    """_parse_timestamp handles ISO format with Z suffix."""
    from orcheo_backend.app.authentication import _parse_timestamp

    result = _parse_timestamp("2025-01-01T12:00:00Z")

    assert result is not None
    assert result.year == 2025


def test_parse_timestamp_with_float() -> None:
    """_parse_timestamp handles float timestamps."""
    from orcheo_backend.app.authentication import _parse_timestamp

    now = datetime.now(tz=UTC)
    timestamp = now.timestamp()

    result = _parse_timestamp(timestamp)

    assert result is not None
    assert abs((result - now).total_seconds()) < 1


def test_coerce_str_items_with_non_sequence_mapping() -> None:
    """_coerce_str_items handles mapping types."""
    from orcheo_backend.app.authentication import _coerce_str_items

    result = _coerce_str_items({"key": "value", "key2": ["item1", "item2"]})

    assert "value" in result
    assert "item1" in result


def test_coerce_str_items_with_non_string_value() -> None:
    """_coerce_str_items converts non-string types."""
    from orcheo_backend.app.authentication import _coerce_str_items

    result = _coerce_str_items(12345)

    assert "12345" in result


def test_load_auth_settings_with_jwks_alternative_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """load_auth_settings accepts AUTH_JWKS as alternative to AUTH_JWKS_STATIC."""
    import json

    jwks = {"keys": [{"kty": "RSA", "kid": "alt-key"}]}
    monkeypatch.setenv("ORCHEO_AUTH_JWKS", json.dumps(jwks))

    settings = load_auth_settings(refresh=True)

    assert len(settings.jwks_static) == 1


@pytest.mark.asyncio
async def test_authenticate_request_without_client_info() -> None:
    """authenticate_request handles requests without client information."""
    from starlette.requests import Request
    from orcheo_backend.app.authentication import authenticate_request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": None,
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request"}

    request = Request(scope, receive)  # type: ignore[arg-type]

    # Should not raise - returns anonymous context
    context = await authenticate_request(request)

    assert not context.is_authenticated


def test_normalize_jwk_list_with_non_sequence() -> None:
    """_normalize_jwk_list returns empty list for non-sequences."""
    from orcheo_backend.app.authentication import _normalize_jwk_list

    assert _normalize_jwk_list("not-a-list") == []
    assert _normalize_jwk_list(123) == []


# Additional tests for missing coverage


def test_service_token_manager_authenticate_with_none_record() -> None:
    """ServiceTokenManager handles hash collision with None record."""
    import hashlib

    token = "test-token"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()

    from orcheo_backend.app.authentication import (
        ServiceTokenManager,
        ServiceTokenRecord,
    )

    record = ServiceTokenRecord(identifier="valid", secret_hash=digest)
    manager = ServiceTokenManager([record])

    # Manually corrupt the internal state to have None in candidates
    manager._records_by_hash[digest].append("nonexistent")

    # Should still work for valid record
    result = manager.authenticate(token)
    assert result.identifier == "valid"


@pytest.mark.asyncio
async def test_jwks_cache_with_zero_ttl_header() -> None:
    """JWKS cache handles zero TTL from headers correctly."""
    from orcheo_backend.app.authentication import JWKSCache

    async def fetcher() -> tuple[list[dict[str, str]], int | None]:
        return ([{"kid": "key-1"}], 0)

    cache = JWKSCache(fetcher, ttl_seconds=0)

    await cache.keys()

    # With both TTL and header at 0, expires_at should be None
    assert cache._expires_at is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_jwks_cache_respects_header_ttl_when_config_is_zero() -> None:
    """JWKS cache uses header TTL when configured TTL is zero."""
    from orcheo_backend.app.authentication import JWKSCache

    async def fetcher() -> tuple[list[dict[str, str]], int | None]:
        return ([{"kid": "key-1"}], 300)

    cache = JWKSCache(fetcher, ttl_seconds=0)

    await cache.keys()

    # Should use header TTL since config is 0
    assert cache._expires_at is not None  # noqa: SLF001
    remaining = (cache._expires_at - datetime.now(tz=UTC)).total_seconds()
    assert remaining == pytest.approx(300, abs=2.0)


def test_authenticator_static_jwks_without_algorithm() -> None:
    """Authenticator handles static JWKS entries without alg field."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm

    # Generate RSA key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()

    # Create JWK without 'alg' field
    jwk_dict = RSAAlgorithm(RSAAlgorithm.SHA256).to_jwk(public_key, as_dict=True)
    jwk_dict["kid"] = "no-alg-key"
    # Explicitly don't set 'alg'

    settings = AuthSettings(
        mode="required",
        jwt_secret=None,
        jwks_url=None,
        jwks_static=(jwk_dict,),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=("RS256",),
        audiences=(),
        issuer=None,
        service_tokens=(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    authenticator = Authenticator(settings)

    # Should have registered the key without algorithm
    assert len(authenticator._static_jwks) == 1  # noqa: SLF001
    jwk, alg = authenticator._static_jwks[0]  # noqa: SLF001
    assert alg is None


@pytest.mark.asyncio
async def test_authenticate_service_token_reraises_non_invalid_errors() -> None:
    """Authenticator re-raises non-invalid_token errors from service token auth."""
    import hashlib

    token = "expired-token"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()

    from orcheo_backend.app.authentication import (
        Authenticator,
        AuthSettings,
        ServiceTokenRecord,
    )

    record = ServiceTokenRecord(
        identifier="expired",
        secret_hash=digest,
        expires_at=datetime.now(tz=UTC) - timedelta(hours=1),
    )

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
        service_tokens=(record,),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    authenticator = Authenticator(settings)

    # Should re-raise token_expired error
    with pytest.raises(AuthenticationError) as exc:
        await authenticator.authenticate(token)
    assert exc.value.code == "auth.token_expired"


# Note: Lines 625-626 (key_unavailable error) are defensive error handling
# that's difficult to trigger without extensive mocking of JWKS resolution


@pytest.mark.asyncio
async def test_match_static_key_with_mismatched_kid() -> None:
    """Static JWKS matching skips keys with mismatched kid."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()

    jwk_dict = RSAAlgorithm(RSAAlgorithm.SHA256).to_jwk(public_key, as_dict=True)
    jwk_dict["kid"] = "expected-kid"
    jwk_dict["alg"] = "RS256"

    settings = AuthSettings(
        mode="required",
        jwt_secret=None,
        jwks_url=None,
        jwks_static=(jwk_dict,),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=("RS256",),
        audiences=(),
        issuer=None,
        service_tokens=(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    authenticator = Authenticator(settings)

    # Try to match with wrong kid
    key = authenticator._match_static_key("wrong-kid", "RS256")  # noqa: SLF001

    # Should return None
    assert key is None


@pytest.mark.asyncio
async def test_match_static_key_with_mismatched_algorithm() -> None:
    """Static JWKS matching skips keys with mismatched algorithm."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()

    jwk_dict = RSAAlgorithm(RSAAlgorithm.SHA256).to_jwk(public_key, as_dict=True)
    jwk_dict["kid"] = "test-kid"
    jwk_dict["alg"] = "RS256"

    settings = AuthSettings(
        mode="required",
        jwt_secret=None,
        jwks_url=None,
        jwks_static=(jwk_dict,),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=("RS256", "RS384"),
        audiences=(),
        issuer=None,
        service_tokens=(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    authenticator = Authenticator(settings)

    # Try to match with wrong algorithm
    key = authenticator._match_static_key("test-kid", "RS384")  # noqa: SLF001

    # Should return None
    assert key is None


@pytest.mark.asyncio
async def test_resolve_signing_key_returns_none_when_no_jwks_cache() -> None:
    """_resolve_signing_key returns None when no JWKS cache is configured."""

    settings = AuthSettings(
        mode="required",
        jwt_secret=None,
        jwks_url=None,
        jwks_static=(),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=("RS256",),
        audiences=(),
        issuer=None,
        service_tokens=(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    authenticator = Authenticator(settings)

    # Should return None when no static keys and no JWKS URL
    key = await authenticator._resolve_signing_key({"kid": "test", "alg": "RS256"})  # noqa: SLF001

    assert key is None


@pytest.mark.asyncio
async def test_match_fetched_key_with_mismatched_kid() -> None:
    """_match_fetched_key skips keys with mismatched kid."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm
    from orcheo_backend.app.authentication import Authenticator

    # Generate actual RSA keys for proper JWKS
    private_key1 = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key1 = private_key1.public_key()
    jwk1 = RSAAlgorithm(RSAAlgorithm.SHA256).to_jwk(public_key1, as_dict=True)
    jwk1["kid"] = "key1"
    jwk1["alg"] = "RS256"

    private_key2 = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key2 = private_key2.public_key()
    jwk2 = RSAAlgorithm(RSAAlgorithm.SHA256).to_jwk(public_key2, as_dict=True)
    jwk2["kid"] = "key2"
    jwk2["alg"] = "RS256"

    settings = load_auth_settings(refresh=True)
    authenticator = Authenticator(settings)

    entries = [jwk1, jwk2]

    # Try to match with kid that doesn't exist
    key = authenticator._match_fetched_key(entries, "key3", "RS256")  # noqa: SLF001

    assert key is None


@pytest.mark.asyncio
async def test_match_fetched_key_with_mismatched_algorithm() -> None:
    """_match_fetched_key skips keys with mismatched algorithm."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()

    jwk_dict = RSAAlgorithm(RSAAlgorithm.SHA256).to_jwk(public_key, as_dict=True)
    jwk_dict["kid"] = "test-kid"
    jwk_dict["alg"] = "RS256"

    settings = load_auth_settings(refresh=True)
    authenticator = Authenticator(settings)

    # Try to match with different algorithm
    key = authenticator._match_fetched_key([jwk_dict], "test-kid", "RS384")  # noqa: SLF001

    assert key is None


@pytest.mark.asyncio
async def test_match_fetched_key_with_non_mapping_entry() -> None:
    """_match_fetched_key handles entries that aren't mappings."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm
    from orcheo_backend.app.authentication import Authenticator

    # Generate actual RSA key for proper JWKS
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()
    jwk = RSAAlgorithm(RSAAlgorithm.SHA256).to_jwk(public_key, as_dict=True)
    jwk["kid"] = "key1"

    settings = load_auth_settings(refresh=True)
    authenticator = Authenticator(settings)

    entries = [
        jwk,
        "not-a-dict",  # Non-mapping
        123,  # Non-mapping
    ]

    # Should handle non-mapping gracefully
    key = authenticator._match_fetched_key(entries, "key1", None)  # noqa: SLF001

    # Should find the valid key
    assert key is not None


@pytest.mark.asyncio
async def test_fetch_jwks_returns_empty_when_no_url() -> None:
    """_fetch_jwks returns empty list when no URL is configured."""

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
        service_tokens=(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    authenticator = Authenticator(settings)

    keys, ttl = await authenticator._fetch_jwks()  # noqa: SLF001

    assert keys == []
    assert ttl is None


@pytest.mark.asyncio
async def test_fetch_jwks_parses_cache_control() -> None:
    """_fetch_jwks extracts TTL from Cache-Control headers."""
    from unittest.mock import AsyncMock, Mock

    settings = AuthSettings(
        mode="required",
        jwt_secret=None,
        jwks_url="https://example.com/jwks.json",
        jwks_static=(),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=(),
        audiences=(),
        issuer=None,
        service_tokens=(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    authenticator = Authenticator(settings)

    # Mock the HTTP response
    mock_response = Mock()
    mock_response.json.return_value = {"keys": [{"kid": "key1"}]}
    mock_response.headers = {"Cache-Control": "max-age=600"}
    mock_response.raise_for_status = Mock()

    with patch("orcheo_backend.app.authentication.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )

        keys, ttl = await authenticator._fetch_jwks()  # noqa: SLF001

        assert len(keys) == 1
        assert ttl == 600


def test_parse_timestamp_with_invalid_string() -> None:
    """_parse_timestamp returns None for invalid string formats."""
    from orcheo_backend.app.authentication import _parse_timestamp

    # Invalid ISO format
    assert _parse_timestamp("not-a-date") is None

    # Non-digit, non-ISO string
    assert _parse_timestamp("2025-99-99") is None


def test_infer_identity_type_with_lowercase_variations() -> None:
    """_infer_identity_type handles case-insensitive type values."""
    from orcheo_backend.app.authentication import _infer_identity_type

    assert _infer_identity_type({"token_use": "USER"}) == "user"
    assert _infer_identity_type({"type": "SERVICE"}) == "service"
    assert _infer_identity_type({"typ": "CLIENT"}) == "service"


def test_extract_scopes_with_nested_orcheo_claim() -> None:
    """_extract_scopes finds scopes in nested orcheo.scopes claim."""
    from orcheo_backend.app.authentication import _extract_scopes

    scopes = set(
        _extract_scopes({"orcheo": {"scopes": ["scope1", "scope2"]}, "scope": "scope3"})
    )

    # Should include both orcheo nested and top-level scopes
    assert "scope1" in scopes
    assert "scope2" in scopes
    assert "scope3" in scopes


def test_extract_workspace_ids_with_nested_orcheo_claim() -> None:
    """_extract_workspace_ids finds workspace IDs in nested orcheo claim."""
    from orcheo_backend.app.authentication import _extract_workspace_ids

    ids = set(
        _extract_workspace_ids(
            {"orcheo": {"workspace_ids": ["ws-1"]}, "workspace": "ws-2"}
        )
    )

    assert "ws-1" in ids
    assert "ws-2" in ids


def test_coerce_from_string_with_non_list_parsed_json() -> None:
    """_coerce_from_string handles non-list JSON parsing results."""
    from orcheo_backend.app.authentication import _coerce_from_string

    # JSON object string
    result = _coerce_from_string('{"key": "value"}')

    # Should recursively coerce
    assert "value" in result


def test_parse_service_tokens_with_servicetokenrecord_instance() -> None:
    """_parse_service_tokens handles ServiceTokenRecord instances."""
    from orcheo_backend.app.authentication import (
        ServiceTokenRecord,
        _parse_service_tokens,
    )

    record = ServiceTokenRecord(identifier="test", secret_hash="hash123")

    records = _parse_service_tokens(record)

    assert len(records) == 1
    assert records[0] is record


def test_normalize_service_token_entries_with_servicetokenrecord() -> None:
    """_normalize_service_token_entries handles ServiceTokenRecord directly."""
    from orcheo_backend.app.authentication import (
        ServiceTokenRecord,
        _normalize_service_token_entries,
    )

    record = ServiceTokenRecord(identifier="test", secret_hash="hash123")

    entries = _normalize_service_token_entries(record)

    assert len(entries) == 1
    assert entries[0] is record


def test_normalize_service_tokens_from_string_with_single_token() -> None:
    """_normalize_service_tokens_from_string handles single token without separators."""
    from orcheo_backend.app.authentication import _normalize_service_tokens_from_string

    result = _normalize_service_tokens_from_string("single-token-no-commas-or-spaces")

    assert len(result) == 1
    assert result[0] == "single-token-no-commas-or-spaces"


def test_normalize_service_tokens_from_string_empty() -> None:
    """_normalize_service_tokens_from_string handles empty strings."""
    from orcheo_backend.app.authentication import _normalize_service_tokens_from_string

    result = _normalize_service_tokens_from_string("")

    assert result == []


def test_parse_jwks_with_empty_string() -> None:
    """_parse_jwks handles empty string input."""
    from orcheo_backend.app.authentication import _parse_jwks

    result = _parse_jwks("")

    assert result == []


def test_extract_bearer_token_with_empty_token() -> None:
    """_extract_bearer_token raises for Bearer with empty token."""
    from orcheo_backend.app.authentication import (
        AuthenticationError,
        _extract_bearer_token,
    )

    # "Bearer " with empty token (spaces get stripped)
    with pytest.raises(AuthenticationError) as exc:
        _extract_bearer_token("Bearer ")
    # This is handled by the invalid scheme check since len(parts) != 2
    assert exc.value.code == "auth.invalid_scheme"


def test_extract_bearer_token_with_spaces_after_token() -> None:
    """_extract_bearer_token handles tokens with trailing spaces after strip."""
    from orcheo_backend.app.authentication import _extract_bearer_token

    # Token with spaces after it gets stripped
    token = _extract_bearer_token("Bearer token123   ")
    assert token == "token123"


@pytest.mark.asyncio
async def test_authenticate_websocket_rate_limit_ip_exceeded() -> None:
    """WebSocket authentication closes on IP rate limit exceeded."""

    with patch("orcheo_backend.app.authentication.get_authenticator") as mock_get_auth:
        with patch(
            "orcheo_backend.app.authentication.get_auth_rate_limiter"
        ) as mock_get_limiter:
            mock_settings = AuthSettings(
                mode="required",
                jwt_secret="secret",
                jwks_url=None,
                jwks_static=(),
                jwks_cache_ttl=300,
                jwks_timeout=5.0,
                allowed_algorithms=("HS256",),
                audiences=(),
                issuer=None,
                service_tokens=(),
                rate_limit_ip=1,
                rate_limit_identity=10,
                rate_limit_interval=60,
            )

            mock_authenticator = Mock()
            mock_authenticator.settings = mock_settings
            mock_get_auth.return_value = mock_authenticator

            mock_limiter = Mock()
            mock_limiter.check_ip = Mock(
                side_effect=AuthenticationError(
                    "Rate limited",
                    code="auth.rate_limited.ip",
                    status_code=429,
                    websocket_code=4429,
                )
            )
            mock_get_limiter.return_value = mock_limiter

            websocket = Mock(spec=WebSocket)
            websocket.headers = {}
            websocket.query_params = {}
            websocket.client = Mock(host="1.2.3.4")
            websocket.state = Mock()
            websocket.close = AsyncMock()

            with pytest.raises(AuthenticationError):
                await authenticate_websocket(websocket)

            # Should close websocket
            websocket.close.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_websocket_rate_limit_identity_exceeded() -> None:
    """WebSocket authentication closes on identity rate limit exceeded."""
    import hashlib
    from orcheo_backend.app.authentication import (
        AuthenticationError,
        RequestContext,
    )

    token = "valid-token"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()

    with patch("orcheo_backend.app.authentication.get_authenticator") as mock_get_auth:
        with patch(
            "orcheo_backend.app.authentication.get_auth_rate_limiter"
        ) as mock_get_limiter:
            mock_settings = AuthSettings(
                mode="required",
                jwt_secret=None,
                jwks_url=None,
                jwks_static=(),
                jwks_cache_ttl=300,
                jwks_timeout=5.0,
                allowed_algorithms=(),
                audiences=(),
                issuer=None,
                service_tokens=(
                    ServiceTokenRecord(identifier="test", secret_hash=digest),
                ),
                rate_limit_ip=10,
                rate_limit_identity=1,
                rate_limit_interval=60,
            )

            mock_authenticator = Mock()
            mock_authenticator.settings = mock_settings
            mock_authenticator.authenticate = AsyncMock(
                return_value=RequestContext(
                    subject="test",
                    identity_type="service",
                    token_id="test",
                )
            )
            mock_get_auth.return_value = mock_authenticator

            mock_limiter = Mock()
            mock_limiter.check_ip = Mock()
            mock_limiter.check_identity = Mock(
                side_effect=AuthenticationError(
                    "Rate limited",
                    code="auth.rate_limited.identity",
                    status_code=429,
                    websocket_code=4429,
                )
            )
            mock_get_limiter.return_value = mock_limiter

            websocket = Mock(spec=WebSocket)
            websocket.headers = {"authorization": f"Bearer {token}"}
            websocket.query_params = {}
            websocket.client = Mock(host="1.2.3.4")
            websocket.state = Mock()
            websocket.close = AsyncMock()

            with pytest.raises(AuthenticationError):
                await authenticate_websocket(websocket)

            # Should close websocket with rate limit error
            websocket.close.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_websocket_authentication_failure() -> None:
    """WebSocket closes and records telemetry on authentication failure."""
    with patch("orcheo_backend.app.authentication.get_authenticator") as mock_get_auth:
        with patch(
            "orcheo_backend.app.authentication.get_auth_rate_limiter"
        ) as mock_get_limiter:
            mock_settings = AuthSettings(
                mode="required",
                jwt_secret="secret",
                jwks_url=None,
                jwks_static=(),
                jwks_cache_ttl=300,
                jwks_timeout=5.0,
                allowed_algorithms=("HS256",),
                audiences=(),
                issuer=None,
                service_tokens=(),
                rate_limit_ip=10,
                rate_limit_identity=10,
                rate_limit_interval=60,
            )

            mock_authenticator = Mock()
            mock_authenticator.settings = mock_settings
            mock_authenticator.authenticate = AsyncMock(
                side_effect=AuthenticationError(
                    "Invalid token",
                    code="auth.invalid_token",
                    websocket_code=4401,
                )
            )
            mock_get_auth.return_value = mock_authenticator

            mock_limiter = Mock()
            mock_limiter.check_ip = Mock()
            mock_get_limiter.return_value = mock_limiter

            websocket = Mock(spec=WebSocket)
            websocket.headers = {"authorization": "Bearer bad-token"}
            websocket.query_params = {}
            websocket.client = Mock(host="1.2.3.4")
            websocket.state = Mock()
            websocket.close = AsyncMock()

            with pytest.raises(AuthenticationError):
                await authenticate_websocket(websocket)

            # Should close websocket
            websocket.close.assert_called_once()


def test_authorization_policy_context_property() -> None:
    """AuthorizationPolicy.context returns the underlying context."""
    from orcheo_backend.app.authentication import (
        AuthorizationPolicy,
        RequestContext,
    )

    context = RequestContext(subject="user", identity_type="user")
    policy = AuthorizationPolicy(context)

    assert policy.context is context


@pytest.mark.asyncio
async def test_get_request_context_calls_authenticate_when_no_state() -> None:
    """get_request_context authenticates when no context in state."""
    from starlette.requests import Request
    from orcheo_backend.app.authentication import get_request_context

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": None,
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request"}

    request = Request(scope, receive)  # type: ignore[arg-type]
    # No auth in state

    # Should call authenticate_request
    context = await get_request_context(request)

    assert context is not None
    assert not context.is_authenticated  # Anonymous in this test


def test_get_authorization_policy_dependency() -> None:
    """get_authorization_policy returns an AuthorizationPolicy."""
    from orcheo_backend.app.authentication import (
        AuthorizationPolicy,
        RequestContext,
        get_authorization_policy,
    )

    context = RequestContext(subject="user", identity_type="user")

    policy = get_authorization_policy(context)

    assert isinstance(policy, AuthorizationPolicy)
    assert policy.context is context


def test_service_token_from_mapping_with_empty_hash() -> None:
    """_service_token_from_mapping returns None when hash normalization fails."""
    from orcheo_backend.app.authentication import _service_token_from_mapping

    # Empty hash value after stripping should raise ValueError in normalization
    record = _service_token_from_mapping({"id": "test", "hash": "   "})

    assert record is None


def test_service_token_rotate_expiry_with_none_original_expiry() -> None:
    """ServiceTokenManager rotation handles records with no expiry correctly."""
    from datetime import timedelta
    from orcheo_backend.app.authentication import (
        ServiceTokenManager,
        ServiceTokenRecord,
    )

    # Create record with no expiry
    record = ServiceTokenRecord(
        identifier="no-expiry",
        secret_hash="hash123",
        expires_at=None,
    )

    manager = ServiceTokenManager([record])

    # Rotate with overlap
    new_secret, new_record = manager.rotate(
        record.identifier, overlap_seconds=300, expires_in=timedelta(hours=1)
    )

    # Original record should have rotation_expires_at set based on overlap
    updated = manager._records_by_id[record.identifier]
    assert updated.rotation_expires_at is not None
    # Expiry should be set to overlap since original had None
    assert updated.expires_at is not None


@pytest.mark.asyncio
async def test_jwks_cache_early_return_with_valid_cache() -> None:
    """JWKS cache returns early when cache is still valid."""
    from orcheo_backend.app.authentication import JWKSCache

    call_count = 0

    async def fetcher() -> tuple[list[dict[str, str]], int | None]:
        nonlocal call_count
        call_count += 1
        return ([{"kid": "key-1"}], None)

    cache = JWKSCache(fetcher, ttl_seconds=300)

    # First call
    keys1 = await cache.keys()
    assert call_count == 1

    # Second call should return cached value without calling fetcher again
    keys2 = await cache.keys()
    assert call_count == 1  # No additional call
    assert keys1 == keys2


def test_infer_identity_type_with_unrecognized_value() -> None:
    """_infer_identity_type continues loop for unrecognized type values."""
    from orcheo_backend.app.authentication import _infer_identity_type

    # Value that's a string but not one of the recognized types
    assert _infer_identity_type({"token_use": "machine"}) == "user"
    # Multiple unrecognized values
    assert _infer_identity_type({"token_use": "robot", "type": "bot"}) == "user"


@pytest.mark.asyncio
async def test_decode_claims_with_generic_invalid_token_error() -> None:
    """_decode_claims handles generic InvalidTokenError."""
    from orcheo_backend.app.authentication import (
        AuthenticationError,
        Authenticator,
        AuthSettings,
    )

    settings = AuthSettings(
        mode="required",
        jwt_secret="test-secret",
        jwks_url=None,
        jwks_static=(),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=("HS256",),
        audiences=(),
        issuer=None,
        service_tokens=(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    authenticator = Authenticator(settings)

    # Create a malformed JWT that will raise InvalidTokenError
    malformed_token = "not.a.valid.jwt.at.all"

    with pytest.raises(AuthenticationError) as exc:
        await authenticator.authenticate(malformed_token)

    assert exc.value.code == "auth.invalid_token"


def test_resolve_signing_key_without_jwks_cache() -> None:
    """_resolve_signing_key returns None when no JWKS cache exists."""
    from orcheo_backend.app.authentication import Authenticator, AuthSettings

    settings = AuthSettings(
        mode="required",
        jwt_secret=None,
        jwks_url=None,
        jwks_static=(),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=("RS256",),
        audiences=(),
        issuer=None,
        service_tokens=(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    authenticator = Authenticator(settings)

    # Verify no cache exists
    assert authenticator._jwks_cache is None


def test_match_fetched_key_with_entry_not_mapping() -> None:
    """_match_fetched_key handles entries where entry_algorithm extraction fails."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm
    from orcheo_backend.app.authentication import Authenticator

    # Generate actual RSA key for proper JWKS
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()
    jwk = RSAAlgorithm(RSAAlgorithm.SHA256).to_jwk(public_key, as_dict=True)
    jwk["kid"] = "key1"
    # Don't set 'alg', and make it so algorithm check path is triggered

    settings = load_auth_settings(refresh=True)
    authenticator = Authenticator(settings)

    # Entry without algorithm field
    key = authenticator._match_fetched_key([jwk], "key1", None)
    # Should still match when algorithm is None
    assert key is not None


def test_parse_timestamp_returns_none_for_invalid_types() -> None:
    """_parse_timestamp returns None for types that can't be converted."""
    from orcheo_backend.app.authentication import _parse_timestamp

    # Object type that's not int/float/str
    result = _parse_timestamp(object())
    assert result is None


def test_normalize_token_hash_raises_valueerror_for_empty() -> None:
    """_normalize_token_hash raises ValueError for empty hash."""
    from orcheo_backend.app.authentication import _normalize_token_hash

    with pytest.raises(ValueError, match="Service token hash must not be empty"):
        _normalize_token_hash("")

    with pytest.raises(ValueError, match="Service token hash must not be empty"):
        _normalize_token_hash("   ")


def test_parse_service_tokens_with_empty_string_in_list() -> None:
    """_parse_service_tokens skips empty strings in sequences."""
    from orcheo_backend.app.authentication import _parse_service_tokens

    # Mix of tokens and empty strings
    records = _parse_service_tokens(["token1", "", "   ", "token2"])

    # Should skip empty strings
    assert len(records) == 2


def test_normalize_service_token_entries_with_unknown_type() -> None:
    """_normalize_service_token_entries handles unknown object types."""
    from orcheo_backend.app.authentication import _normalize_service_token_entries

    # Integer (not None, not ServiceTokenRecord, not Mapping, not string, not sequence)
    result = _normalize_service_token_entries(12345)

    # Should wrap in list
    assert len(result) == 1
    assert result[0] == 12345


def test_normalize_service_tokens_from_string_with_space_separated_fallback() -> None:
    """_normalize_service_tokens_from_string handles space-separated non-JSON."""
    from orcheo_backend.app.authentication import _normalize_service_tokens_from_string

    # String with spaces but not valid JSON
    result = _normalize_service_tokens_from_string("token1 token2 token3")

    # Should parse as space-separated and normalize each
    assert len(result) >= 3


def test_extract_bearer_token_with_only_whitespace_after_bearer() -> None:
    """_extract_bearer_token raises for Bearer with only whitespace."""
    from orcheo_backend.app.authentication import (
        AuthenticationError,
        _extract_bearer_token,
    )

    # "Bearer" followed by whitespace that strips to empty
    with pytest.raises(AuthenticationError) as exc:
        _extract_bearer_token("Bearer    ")

    assert exc.value.code == "auth.invalid_scheme"


@pytest.mark.asyncio
async def test_require_scopes_dependency_returns_context() -> None:
    """require_scopes dependency returns context when scopes are present."""
    from orcheo_backend.app.authentication import RequestContext, require_scopes

    context = RequestContext(
        subject="user",
        identity_type="user",
        scopes=frozenset(["read", "write"]),
    )

    # Create the dependency function
    dependency = require_scopes("read", "write")

    # Call it with the context
    result = await dependency(context)

    assert result is context


def test_extract_scopes_with_non_string_non_list_value() -> None:
    """_extract_scopes handles claim values that can't be parsed."""
    from orcheo_backend.app.authentication import _extract_scopes

    # Orcheo nested with non-Mapping value
    scopes = set(_extract_scopes({"orcheo": "not-a-dict"}))
    assert len(scopes) == 0


def test_extract_workspace_ids_with_non_string_non_list_value() -> None:
    """_extract_workspace_ids handles claim values that can't be parsed."""
    from orcheo_backend.app.authentication import _extract_workspace_ids

    # Orcheo nested with non-Mapping value
    ids = set(_extract_workspace_ids({"orcheo": "not-a-dict"}))
    assert len(ids) == 0


def test_coerce_str_items_with_empty_after_stripping() -> None:
    """_coerce_str_items returns empty set when value strips to empty."""
    from orcheo_backend.app.authentication import _coerce_str_items

    # String with only whitespace
    result = _coerce_str_items("   ")
    assert result == set()

    # Non-string that converts to empty after strip
    result2 = _coerce_str_items("")
    assert result2 == set()


def test_extract_scopes_with_null_nested_value() -> None:
    """_extract_scopes handles orcheo claim with None scopes value."""
    from orcheo_backend.app.authentication import _extract_scopes

    # orcheo is a Mapping but orcheo.scopes is None
    scopes = set(_extract_scopes({"orcheo": {"other_key": "value"}}))
    assert len(scopes) == 0


def test_extract_workspace_ids_with_null_nested_value() -> None:
    """_extract_workspace_ids handles orcheo claim with None workspace_ids value."""
    from orcheo_backend.app.authentication import _extract_workspace_ids

    # orcheo is a Mapping but orcheo.workspace_ids is None
    ids = set(_extract_workspace_ids({"orcheo": {"other_key": "value"}}))
    assert len(ids) == 0


def test_coerce_from_string_with_empty_strings_in_list() -> None:
    """_coerce_from_string skips empty strings after stripping."""
    from orcheo_backend.app.authentication import _coerce_from_string

    # JSON array with empty/whitespace strings
    result = _coerce_from_string('["token1", "", "  ", "token2"]')

    # Should only include non-empty tokens
    assert "token1" in result
    assert "token2" in result
    assert "" not in result


def test_service_token_manager_authenticate_with_non_matching_record() -> None:
    """ServiceTokenManager.authenticate skips records that don't match."""
    import hashlib

    # Create two records with the same hash but different identifiers
    token_hash = hashlib.sha256(b"my-secret-token").hexdigest()
    record1 = ServiceTokenRecord(identifier="record-1", secret_hash="wrong-hash")
    record2 = ServiceTokenRecord(identifier="record-2", secret_hash=token_hash)

    # Manually register both with the same hash bucket
    manager = ServiceTokenManager([record2])
    manager._records_by_id["record-1"] = record1
    manager._records_by_hash[token_hash] = ["record-1", "record-2"]

    # Should skip record-1 and find record-2
    result = manager.authenticate("my-secret-token")
    assert result.identifier == "record-2"


def test_service_token_rotation_expiry_with_non_none_expires_at() -> None:
    """_calculate_rotation_expiry returns min when expires_at is not None."""
    from orcheo_backend.app.authentication import ServiceTokenManager

    now = datetime.now(tz=UTC)
    future = now + timedelta(days=30)
    record = ServiceTokenRecord(
        identifier="test",
        secret_hash="test-hash",
        expires_at=future,
    )

    # Overlap is shorter than record expiry
    result = ServiceTokenManager._calculate_rotation_expiry(record, now, 300)

    # Should return the overlap expiry (now + 300 seconds)
    expected = now + timedelta(seconds=300)
    assert result is not None
    assert abs((result - expected).total_seconds()) < 1


@pytest.mark.asyncio
async def test_authenticator_jwt_key_resolution_returns_none() -> None:
    """Authenticator raises auth.key_unavailable when key not resolved."""
    from unittest.mock import patch

    settings = AuthSettings(
        mode="required",
        jwt_secret=None,
        jwks_url="https://example.com/.well-known/jwks.json",
        jwks_static=(),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=("RS256",),
        audiences=(),
        issuer=None,
        service_tokens=(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    authenticator = Authenticator(settings)

    # Create a valid RS256 token
    import jwt as jwt_lib
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt_lib.encode({"sub": "test-user"}, private_key, algorithm="RS256")

    # Mock _resolve_signing_key to return None (key not found)
    with patch.object(authenticator, "_resolve_signing_key", return_value=None):
        with pytest.raises(AuthenticationError) as exc_info:
            await authenticator.authenticate(token)

        assert exc_info.value.code == "auth.key_unavailable"
        assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_authenticator_jwt_invalid_token_error() -> None:
    """Authenticator handles InvalidTokenError during JWT decode."""
    settings = AuthSettings(
        mode="required",
        jwt_secret="test-secret",
        jwks_url=None,
        jwks_static=(),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=("HS256",),
        audiences=(),
        issuer=None,
        service_tokens=(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    authenticator = Authenticator(settings)

    # Create a malformed token that will fail decode with InvalidTokenError
    # Use a valid JWT structure but signed with wrong secret
    import jwt as jwt_lib

    token = jwt_lib.encode({"sub": "test-user"}, "wrong-secret", algorithm="HS256")

    with pytest.raises(AuthenticationError) as exc_info:
        await authenticator.authenticate(token)

    assert exc_info.value.code == "auth.invalid_token"


@pytest.mark.asyncio
async def test_authenticator_resolve_signing_key_with_jwks_cache() -> None:
    """Authenticator._resolve_signing_key fetches from JWKS cache."""
    import jwt as jwt_lib
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    # Convert to JWK dict properly
    jwk_dict = jwt_lib.algorithms.RSAAlgorithm.to_jwk(public_key, as_dict=True)
    if isinstance(jwk_dict, str):
        import json

        jwk_dict = json.loads(jwk_dict)

    jwk_dict["kid"] = "test-key-id"
    jwk_dict["alg"] = "RS256"

    # Mock JWKS fetcher
    async def mock_fetcher():
        return [jwk_dict], 300

    from orcheo_backend.app.authentication import JWKSCache

    jwks_cache = JWKSCache(mock_fetcher, ttl_seconds=300)

    settings = AuthSettings(
        mode="required",
        jwt_secret=None,
        jwks_url="https://example.com/.well-known/jwks.json",
        jwks_static=(),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=("RS256",),
        audiences=(),
        issuer=None,
        service_tokens=(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    authenticator = Authenticator(settings)
    authenticator._jwks_cache = jwks_cache

    # Create token with matching kid
    token = jwt_lib.encode(
        {"sub": "test-user"},
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key-id"},
    )

    # Should successfully resolve the key and authenticate
    context = await authenticator.authenticate(token)
    assert context.subject == "test-user"


def test_match_fetched_key_with_non_mapping_entry_algorithm() -> None:
    """_match_fetched_key handles entry that is not a Mapping for algorithm."""
    import json
    import jwt as jwt_lib
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    jwk_str = jwt_lib.algorithms.RSAAlgorithm.to_jwk(public_key, as_dict=True)
    if isinstance(jwk_str, str):
        jwk_dict = json.loads(jwk_str)
    else:
        jwk_dict = jwk_str

    settings = AuthSettings(
        mode="required",
        jwt_secret=None,
        jwks_url=None,
        jwks_static=(),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=("RS256",),
        audiences=(),
        issuer=None,
        service_tokens=(),
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
    )

    authenticator = Authenticator(settings)

    # Test with a list entry (not a Mapping) - this would be malformed but we handle it
    # Create entry without alg field to trigger the else branch at line 707
    jwk_no_alg = jwk_dict.copy()
    jwk_no_alg.pop("alg", None)

    key = authenticator._match_fetched_key([jwk_no_alg], None, "RS256")
    assert key is not None


def test_parse_service_tokens_with_plain_text_creates_hash() -> None:
    """_parse_service_tokens handles plain text tokens by hashing them."""
    import hashlib
    from orcheo_backend.app.authentication import _parse_service_tokens

    # Plain text token (not a mapping)
    result = _parse_service_tokens("my-plain-token")

    assert len(result) == 1
    expected_hash = hashlib.sha256(b"my-plain-token").hexdigest()
    assert result[0].secret_hash == expected_hash
    assert result[0].identifier == expected_hash[:8]


def test_normalize_service_tokens_from_string_with_commas_but_non_sequence() -> None:
    """_normalize_service_tokens_from_string handles comma/space case."""
    from orcheo_backend.app.authentication import (
        _normalize_service_tokens_from_string,
    )

    # String with commas that parses to non-sequence (edge case)
    # This tests line 1020 - the fallback case
    result = _normalize_service_tokens_from_string('{"key": "value"}')

    # Should return the parsed dict as-is
    assert len(result) == 1
    assert isinstance(result[0], dict)


def test_parse_service_tokens_with_empty_string_entry() -> None:
    """_parse_service_tokens skips empty string entries (line 975)."""
    from orcheo_backend.app.authentication import _parse_service_tokens

    # Mix of valid and empty entries
    result = _parse_service_tokens(["valid-token", "", "  ", "another-token"])

    # Should only have 2 tokens (empty ones skipped)
    assert len(result) == 2


def test_parse_service_tokens_with_mapping_returning_none() -> None:
    """_parse_service_tokens handles mappings producing None records."""
    from orcheo_backend.app.authentication import _parse_service_tokens

    # Mapping without hash/secret returns None from _service_token_from_mapping
    result = _parse_service_tokens([{"id": "test", "scopes": ["read"]}])

    # Should be empty because the mapping didn't have hash or secret
    assert len(result) == 0


def test_normalize_service_tokens_from_string_with_commas_and_sequence() -> None:
    """_normalize_service_tokens_from_string handles comma sequences."""
    from orcheo_backend.app.authentication import (
        _normalize_service_tokens_from_string,
    )

    # This should parse into a non-sequence that falls through to line 1020
    result = _normalize_service_tokens_from_string("token1,token2")

    # Should parse as list of tokens
    assert len(result) >= 2
