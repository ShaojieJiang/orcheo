"""OAuth configuration tests for the CLI."""

from __future__ import annotations
from pathlib import Path
import pytest
from orcheo_sdk.cli.auth.config import (
    AUTH_AUDIENCE_ENV,
    AUTH_CLIENT_ID_ENV,
    AUTH_ISSUER_ENV,
    AUTH_ORGANIZATION_ENV,
    AUTH_SCOPES_ENV,
    DEFAULT_SCOPES,
    get_oauth_config,
    is_oauth_configured,
)
from orcheo_sdk.cli.errors import CLIConfigurationError


@pytest.fixture(autouse=True)
def isolated_config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ensure tests do not read user-level CLI config."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setenv("ORCHEO_CONFIG_DIR", str(config_dir))


def test_is_oauth_configured_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(AUTH_ISSUER_ENV, raising=False)
    monkeypatch.delenv(AUTH_CLIENT_ID_ENV, raising=False)
    assert not is_oauth_configured()


def test_is_oauth_configured_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(AUTH_ISSUER_ENV, "https://auth.example.com")
    monkeypatch.delenv(AUTH_CLIENT_ID_ENV, raising=False)
    assert not is_oauth_configured()


def test_is_oauth_configured_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(AUTH_ISSUER_ENV, "https://auth.example.com")
    monkeypatch.setenv(AUTH_CLIENT_ID_ENV, "client-123")
    assert is_oauth_configured()


def test_get_oauth_config_missing_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(AUTH_ISSUER_ENV, raising=False)
    monkeypatch.setenv(AUTH_CLIENT_ID_ENV, "client-123")
    with pytest.raises(CLIConfigurationError):
        get_oauth_config()


def test_get_oauth_config_missing_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(AUTH_ISSUER_ENV, "https://auth.example.com")
    monkeypatch.delenv(AUTH_CLIENT_ID_ENV, raising=False)
    with pytest.raises(CLIConfigurationError):
        get_oauth_config()


def test_get_oauth_config_minimal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(AUTH_ISSUER_ENV, "https://auth.example.com/")
    monkeypatch.setenv(AUTH_CLIENT_ID_ENV, "client-123")
    monkeypatch.delenv(AUTH_SCOPES_ENV, raising=False)
    monkeypatch.delenv(AUTH_AUDIENCE_ENV, raising=False)
    monkeypatch.delenv(AUTH_ORGANIZATION_ENV, raising=False)

    config = get_oauth_config()

    assert config.issuer == "https://auth.example.com"  # trailing slash stripped
    assert config.client_id == "client-123"
    assert config.scopes == DEFAULT_SCOPES
    assert config.audience is None
    assert config.organization is None


def test_get_oauth_config_full(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(AUTH_ISSUER_ENV, "https://auth.example.com")
    monkeypatch.setenv(AUTH_CLIENT_ID_ENV, "client-123")
    monkeypatch.setenv(AUTH_SCOPES_ENV, "openid email custom:scope")
    monkeypatch.setenv(AUTH_AUDIENCE_ENV, "https://api.example.com")
    monkeypatch.setenv(AUTH_ORGANIZATION_ENV, "org_abc123")

    config = get_oauth_config()

    assert config.issuer == "https://auth.example.com"
    assert config.client_id == "client-123"
    assert config.scopes == "openid email custom:scope"
    assert config.audience == "https://api.example.com"
    assert config.organization == "org_abc123"


def test_get_oauth_config_from_profile_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from orcheo_sdk.cli.config import CONFIG_FILENAME

    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / CONFIG_FILENAME
    config_file.write_text(
        "\n".join(
            [
                "[profiles.default]",
                'auth_issuer = "https://profile.example.com/"',
                'auth_client_id = "profile-client"',
                'auth_scopes = "openid profile"',
                'auth_audience = "https://api.profile.example.com"',
                'auth_organization = "org_profile"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("ORCHEO_CONFIG_DIR", str(config_dir))
    monkeypatch.delenv(AUTH_ISSUER_ENV, raising=False)
    monkeypatch.delenv(AUTH_CLIENT_ID_ENV, raising=False)
    monkeypatch.delenv(AUTH_SCOPES_ENV, raising=False)
    monkeypatch.delenv(AUTH_AUDIENCE_ENV, raising=False)
    monkeypatch.delenv(AUTH_ORGANIZATION_ENV, raising=False)

    config = get_oauth_config()

    assert config.issuer == "https://profile.example.com"
    assert config.client_id == "profile-client"
    assert config.scopes == "openid profile"
    assert config.audience == "https://api.profile.example.com"
    assert config.organization == "org_profile"


def test_load_profile_invalid_toml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test that invalid TOML in config raises CLIConfigurationError."""
    from orcheo_sdk.cli.config import CONFIG_FILENAME

    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / CONFIG_FILENAME
    config_file.write_text("this is not valid toml [[[", encoding="utf-8")

    monkeypatch.setenv("ORCHEO_CONFIG_DIR", str(config_dir))
    monkeypatch.delenv(AUTH_ISSUER_ENV, raising=False)
    monkeypatch.delenv(AUTH_CLIENT_ID_ENV, raising=False)

    with pytest.raises(CLIConfigurationError, match="Invalid TOML"):
        get_oauth_config()


def test_coerce_str_returns_none_for_non_string() -> None:
    """Test _coerce_str returns None for non-string values."""
    from orcheo_sdk.cli.auth.config import _coerce_str

    assert _coerce_str(123) is None
    assert _coerce_str(None) is None
    assert _coerce_str(["a"]) is None
    assert _coerce_str("hello") == "hello"
