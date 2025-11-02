"""Tests for the FastAPI authentication dependencies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from orcheo_backend.app import create_app
from orcheo_backend.app.authentication import (
    JWKSCache,
    authenticate_request,
    reset_authentication_state,
)
from orcheo_backend.app.repository import InMemoryWorkflowRepository


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
    ):
        monkeypatch.delenv(key, raising=False)
    reset_authentication_state()
    yield
    monkeypatch.undo()
    reset_authentication_state()


def _client() -> TestClient:
    repository = InMemoryWorkflowRepository()
    return TestClient(create_app(repository=repository))


def test_requests_allowed_when_auth_disabled() -> None:
    """Requests succeed when no authentication configuration is provided."""

    client = _client()
    response = client.get("/api/workflows")
    assert response.status_code == 200


def test_service_token_required_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing Authorization header yields 401 when service tokens are configured."""

    monkeypatch.setenv("ORCHEO_AUTH_SERVICE_TOKENS", '["secret-token"]')
    reset_authentication_state()

    client = _client()
    response = client.get("/api/workflows")

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    detail = response.json()["detail"]
    assert detail["code"] == "auth.missing_token"


def test_valid_service_token_allows_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """Providing a valid service token authorizes the request."""

    monkeypatch.setenv("ORCHEO_AUTH_SERVICE_TOKENS", '["ci-token"]')
    reset_authentication_state()

    client = _client()
    response = client.get(
        "/api/workflows",
        headers={"Authorization": "Bearer ci-token"},
    )

    assert response.status_code == 200


def test_invalid_service_token_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Incorrect service tokens result in a 401 response."""

    monkeypatch.setenv("ORCHEO_AUTH_SERVICE_TOKENS", '["ci-token"]')
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

    monkeypatch.setenv(
        "ORCHEO_AUTH_SERVICE_TOKENS",
        '{"id": "ci", "secret": "token-123", "scopes": ["workflows:read"], "workspace_ids": ["ws-1"]}',
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
