"""Bootstrap configuration parsing tests."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
import pytest
from orcheo_backend.app.authentication import (
    _parse_timestamp,
    load_auth_settings,
    reset_authentication_state,
)
from tests.backend.authentication_test_utils import reset_auth_state


@pytest.fixture(autouse=True)
def _reset_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure authentication state is cleared between tests."""

    yield from reset_auth_state(monkeypatch)


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
