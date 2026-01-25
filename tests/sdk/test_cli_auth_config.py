"""OAuth configuration tests for the CLI."""

from __future__ import annotations
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
