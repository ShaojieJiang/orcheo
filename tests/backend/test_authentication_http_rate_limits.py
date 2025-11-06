"""HTTP authentication rate-limiting and telemetry tests."""

from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from orcheo_backend.app.authentication import (
    auth_telemetry,
    reset_authentication_state,
)
from tests.backend.authentication_test_utils import (
    _setup_service_token,
    create_test_client,
    reset_auth_state,
)


def _client() -> TestClient:
    """Create a fresh TestClient for rate limiting scenarios."""

    return create_test_client()


@pytest.fixture(autouse=True)
def _reset_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure authentication state is cleared between tests."""

    yield from reset_auth_state(monkeypatch)


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
