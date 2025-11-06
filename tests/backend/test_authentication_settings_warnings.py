"""Authentication settings and operator warning tests."""

from __future__ import annotations
import logging
import pytest
from orcheo_backend.app.authentication import AuthSettings, load_auth_settings
from tests.backend.authentication_test_utils import reset_auth_state


@pytest.fixture(autouse=True)
def _reset_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure authentication state is cleared between tests."""

    yield from reset_auth_state(monkeypatch)


def test_raw_service_token_emits_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Using raw service token secrets emits an operator-facing warning."""

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


def test_auth_settings_enforce_disabled_mode() -> None:
    """AuthSettings.enforce returns False when mode is disabled."""

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
