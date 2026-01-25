"""OAuth token refresh tests for the CLI."""

from __future__ import annotations
import time
from pathlib import Path
import pytest
import orcheo_sdk.cli.auth.refresh as refresh_module
from orcheo_sdk.cli.auth.refresh import get_valid_access_token, refresh_oauth_tokens
from orcheo_sdk.cli.auth.tokens import AuthTokens, set_oauth_tokens


@pytest.fixture()
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setenv("ORCHEO_CONFIG_DIR", str(config))
    return config


def test_get_valid_access_token_oauth_not_configured(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ORCHEO_AUTH_ISSUER", raising=False)
    monkeypatch.delenv("ORCHEO_AUTH_CLIENT_ID", raising=False)

    result = get_valid_access_token(profile="default")
    assert result is None


def test_get_valid_access_token_no_tokens(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORCHEO_AUTH_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("ORCHEO_AUTH_CLIENT_ID", "client-123")

    result = get_valid_access_token(profile="default")
    assert result is None


def test_get_valid_access_token_valid_token(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORCHEO_AUTH_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("ORCHEO_AUTH_CLIENT_ID", "client-123")

    future = int(time.time() * 1000) + 3600000
    tokens = AuthTokens(access_token="valid-token", expires_at=future)
    set_oauth_tokens(profile="default", tokens=tokens)

    result = get_valid_access_token(profile="default")
    assert result == "valid-token"


def test_get_valid_access_token_expired_no_refresh(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORCHEO_AUTH_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("ORCHEO_AUTH_CLIENT_ID", "client-123")

    past = int(time.time() * 1000) - 3600000
    tokens = AuthTokens(access_token="expired-token", expires_at=past)
    set_oauth_tokens(profile="default", tokens=tokens)

    result = get_valid_access_token(profile="default")
    assert result is None


def test_refresh_oauth_tokens_no_refresh_token(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORCHEO_AUTH_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("ORCHEO_AUTH_CLIENT_ID", "client-123")

    past = int(time.time() * 1000) - 3600000
    tokens = AuthTokens(
        access_token="expired-token", expires_at=past, refresh_token=None
    )
    set_oauth_tokens(profile="default", tokens=tokens)

    result = refresh_oauth_tokens(profile="default")
    assert result is None


def test_refresh_oauth_tokens_not_configured(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ORCHEO_AUTH_ISSUER", raising=False)
    monkeypatch.delenv("ORCHEO_AUTH_CLIENT_ID", raising=False)

    result = refresh_oauth_tokens(profile="default")
    assert result is None


def test_refresh_oauth_tokens_invalid_discovery_json(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORCHEO_AUTH_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("ORCHEO_AUTH_CLIENT_ID", "client-123")

    tokens = AuthTokens(
        access_token="expired-token", expires_at=0, refresh_token="refresh-token"
    )
    set_oauth_tokens(profile="default", tokens=tokens)

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            raise ValueError("invalid json")

    monkeypatch.setattr(
        refresh_module.httpx, "get", lambda *args, **kwargs: DummyResponse()
    )
    monkeypatch.setattr(
        refresh_module.httpx,
        "post",
        lambda *args, **kwargs: pytest.fail("httpx.post should not be called"),
    )

    result = refresh_oauth_tokens(profile="default")
    assert result is None
