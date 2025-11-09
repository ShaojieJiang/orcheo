from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from orcheo_backend.app import app
from orcheo_backend.app.authentication.dependencies import reset_authentication_state


def _configure_dev_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORCHEO_AUTH_DEV_LOGIN_ENABLED", "true")
    monkeypatch.setenv("ORCHEO_AUTH_DEV_COOKIE_NAME", "orcheo_dev_session")
    monkeypatch.setenv(
        "ORCHEO_AUTH_DEV_SCOPES",
        "workflows:read,workflows:write,workflows:execute",
    )
    reset_authentication_state()


def _clear_dev_login(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [
        "ORCHEO_AUTH_DEV_LOGIN_ENABLED",
        "ORCHEO_AUTH_DEV_COOKIE_NAME",
        "ORCHEO_AUTH_DEV_SCOPES",
    ]:
        monkeypatch.delenv(key, raising=False)
    reset_authentication_state()


def test_dev_login_sets_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure_dev_login(monkeypatch)
    client = TestClient(app)

    response = client.post(
        "/api/auth/dev/login",
        json={"provider": "google", "email": "avery@example.com"},
    )

    assert response.status_code == 200
    assert "orcheo_dev_session" in response.cookies
    assert response.json()["provider"] == "google"

    logout = client.post("/api/auth/dev/logout")
    assert logout.status_code == 204
    assert "orcheo_dev_session" not in logout.cookies


def test_dev_login_disabled_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_dev_login(monkeypatch)
    client = TestClient(app)

    response = client.post("/api/auth/dev/login", json={"provider": "github"})

    assert response.status_code == 404
