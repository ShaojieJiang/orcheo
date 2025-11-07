"""Bootstrap service token HTTP integration tests."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
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
    """Create a FastAPI TestClient for bootstrap HTTP scenarios."""

    return create_test_client()


@pytest.fixture(autouse=True)
def _reset_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure authentication state is cleared between tests."""

    yield from reset_auth_state(monkeypatch)


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


def test_bootstrap_token_rejects_invalid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_bootstrap_token_with_database_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bootstrap token works alongside database-persisted tokens."""

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
