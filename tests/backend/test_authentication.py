"""Tests for the FastAPI authentication dependencies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from orcheo_backend.app import create_app
from orcheo_backend.app.authentication import (
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
