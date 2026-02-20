"""Coverage for _parse_bool branches and dev scopes defaults."""

from __future__ import annotations
import pytest
from orcheo_backend.app.authentication.dependencies import reset_authentication_state
from orcheo_backend.app.authentication.settings import (
    _parse_bool,
    load_auth_settings,
)


@pytest.fixture(autouse=True)
def _reset_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure authentication-related environment is cleared between tests."""

    for key in (
        "ORCHEO_AUTH_DEV_LOGIN_ENABLED",
        "ORCHEO_AUTH_DEV_COOKIE_NAME",
        "ORCHEO_AUTH_DEV_SCOPES",
        "ORCHEO_AUTH_DEV_WORKSPACE_IDS",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_authentication_state()


def test_parse_bool_handles_int_and_strings() -> None:
    """_parse_bool covers int and string truthy/falsey branches."""

    # Int branch
    assert _parse_bool(1, False) is True
    assert _parse_bool(0, True) is False

    # String truthy
    for truth in ("1", "true", "yes", "on", " TrUe "):
        assert _parse_bool(truth, False) is True

    # String falsey
    for falsy in ("0", "false", "no", "off", "  OFF  "):
        assert _parse_bool(falsy, True) is False

    # Unrecognized string should fall back to default
    assert _parse_bool("maybe", True) is True
    assert _parse_bool("unknown", False) is False

    # Non-string/non-int values should also fall back to default
    assert _parse_bool(object(), True) is True
    assert _parse_bool(object(), False) is False


def test_load_auth_settings_default_dev_scopes(monkeypatch: pytest.MonkeyPatch) -> None:
    """When dev login enabled without explicit scopes, defaults are applied."""

    monkeypatch.setenv("ORCHEO_AUTH_DEV_LOGIN_ENABLED", "true")
    monkeypatch.setenv("ORCHEO_AUTH_DEV_COOKIE_NAME", "orcheo_dev_session")
    # Do NOT set ORCHEO_AUTH_DEV_SCOPES to trigger default branch
    reset_authentication_state()

    settings = load_auth_settings(refresh=True)

    # Defaults should include workflows and vault scopes
    assert "workflows:read" in settings.dev_login_scopes
    assert "vault:write" in settings.dev_login_scopes
