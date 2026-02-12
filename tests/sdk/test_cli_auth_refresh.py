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


class DummyResponse:
    def __init__(self, payload: object, status_error: Exception | None = None) -> None:
        self._payload = payload
        self._status_error = status_error

    def raise_for_status(self) -> None:
        if self._status_error:
            raise self._status_error

    def json(self) -> object:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_load_discovery_token_endpoint_payload_not_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        refresh_module.httpx,
        "get",
        lambda *args, **kwargs: DummyResponse(["not", "dict"]),
    )

    result = refresh_module._load_discovery_token_endpoint("https://auth.example.com")
    assert result is None


def test_load_discovery_token_endpoint_invalid_token_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        refresh_module.httpx,
        "get",
        lambda *args, **kwargs: DummyResponse({"token_endpoint": 123}),
    )

    result = refresh_module._load_discovery_token_endpoint("https://auth.example.com")
    assert result is None


def test_get_valid_access_token_oauth_not_configured(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ORCHEO_AUTH_ISSUER", raising=False)
    monkeypatch.delenv("ORCHEO_AUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("ORCHEO_AUTH_AUDIENCE", raising=False)

    result = get_valid_access_token(profile="default")
    assert result is None


def test_get_valid_access_token_no_tokens(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORCHEO_AUTH_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("ORCHEO_AUTH_CLIENT_ID", "client-123")
    monkeypatch.setenv("ORCHEO_AUTH_AUDIENCE", "https://api.example.com")

    result = get_valid_access_token(profile="default")
    assert result is None


def test_get_valid_access_token_valid_token(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORCHEO_AUTH_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("ORCHEO_AUTH_CLIENT_ID", "client-123")
    monkeypatch.setenv("ORCHEO_AUTH_AUDIENCE", "https://api.example.com")

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
    monkeypatch.setenv("ORCHEO_AUTH_AUDIENCE", "https://api.example.com")

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
    monkeypatch.setenv("ORCHEO_AUTH_AUDIENCE", "https://api.example.com")

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
    monkeypatch.delenv("ORCHEO_AUTH_AUDIENCE", raising=False)

    result = refresh_oauth_tokens(profile="default")
    assert result is None


def test_refresh_oauth_tokens_invalid_discovery_json(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORCHEO_AUTH_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("ORCHEO_AUTH_CLIENT_ID", "client-123")
    monkeypatch.setenv("ORCHEO_AUTH_AUDIENCE", "https://api.example.com")

    tokens = AuthTokens(
        access_token="expired-token", expires_at=0, refresh_token="refresh-token"
    )
    set_oauth_tokens(profile="default", tokens=tokens)

    monkeypatch.setattr(
        refresh_module.httpx,
        "get",
        lambda *args, **kwargs: DummyResponse(ValueError("invalid json")),
    )
    monkeypatch.setattr(
        refresh_module.httpx,
        "post",
        lambda *args, **kwargs: pytest.fail("httpx.post should not be called"),
    )

    result = refresh_oauth_tokens(profile="default")
    assert result is None


def test_refresh_oauth_tokens_http_error(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORCHEO_AUTH_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("ORCHEO_AUTH_CLIENT_ID", "client-123")
    monkeypatch.setenv("ORCHEO_AUTH_AUDIENCE", "https://api.example.com")

    tokens = AuthTokens(
        access_token="expired-token", expires_at=0, refresh_token="refresh-token"
    )
    set_oauth_tokens(profile="default", tokens=tokens)

    monkeypatch.setattr(
        refresh_module.httpx,
        "get",
        lambda *args, **kwargs: DummyResponse(
            {"token_endpoint": "https://auth.example.com/token"}
        ),
    )

    def raise_request_error(*args: object, **kwargs: object) -> DummyResponse:
        request = refresh_module.httpx.Request("POST", "https://auth.example.com/token")
        raise refresh_module.httpx.RequestError("boom", request=request)

    monkeypatch.setattr(refresh_module.httpx, "post", raise_request_error)

    result = refresh_oauth_tokens(profile="default")
    assert result is None


def test_refresh_oauth_tokens_missing_access_token(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORCHEO_AUTH_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("ORCHEO_AUTH_CLIENT_ID", "client-123")
    monkeypatch.setenv("ORCHEO_AUTH_AUDIENCE", "https://api.example.com")

    tokens = AuthTokens(
        access_token="expired-token", expires_at=0, refresh_token="refresh-token"
    )
    set_oauth_tokens(profile="default", tokens=tokens)

    monkeypatch.setattr(
        refresh_module.httpx,
        "get",
        lambda *args, **kwargs: DummyResponse(
            {"token_endpoint": "https://auth.example.com/token"}
        ),
    )
    monkeypatch.setattr(
        refresh_module.httpx,
        "post",
        lambda *args, **kwargs: DummyResponse({"token_type": "Bearer"}),
    )

    result = refresh_oauth_tokens(profile="default")
    assert result is None


def test_refresh_oauth_tokens_success_calculates_expiry(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORCHEO_AUTH_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("ORCHEO_AUTH_CLIENT_ID", "client-123")
    monkeypatch.setenv("ORCHEO_AUTH_AUDIENCE", "https://api.example.com")

    tokens = AuthTokens(
        access_token="expired-token",
        expires_at=123,
        refresh_token="refresh-token",
        id_token="old-id",
    )
    set_oauth_tokens(profile="default", tokens=tokens)

    monkeypatch.setattr(
        refresh_module.httpx,
        "get",
        lambda *args, **kwargs: DummyResponse(
            {"token_endpoint": "https://auth.example.com/token"}
        ),
    )
    monkeypatch.setattr(
        refresh_module.httpx,
        "post",
        lambda *args, **kwargs: DummyResponse(
            {
                "access_token": "new-access",
                "id_token": "new-id",
                "refresh_token": "new-refresh",
                "token_type": "Bearer",
                "expires_in": 60,
            }
        ),
    )
    monkeypatch.setattr(refresh_module.time, "time", lambda: 1000.0)

    result = refresh_oauth_tokens(profile="default")
    assert result is not None
    assert result.access_token == "new-access"
    assert result.id_token == "new-id"
    assert result.refresh_token == "new-refresh"
    assert result.token_type == "Bearer"
    assert result.expires_at == 1_060_000


def test_refresh_oauth_tokens_success_fallback_expiry(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ORCHEO_AUTH_ISSUER", "https://auth.example.com")
    monkeypatch.setenv("ORCHEO_AUTH_CLIENT_ID", "client-123")
    monkeypatch.setenv("ORCHEO_AUTH_AUDIENCE", "https://api.example.com")

    tokens = AuthTokens(
        access_token="expired-token", expires_at=456, refresh_token="refresh-token"
    )
    set_oauth_tokens(profile="default", tokens=tokens)

    monkeypatch.setattr(
        refresh_module.httpx,
        "get",
        lambda *args, **kwargs: DummyResponse(
            {"token_endpoint": "https://auth.example.com/token"}
        ),
    )
    monkeypatch.setattr(
        refresh_module.httpx,
        "post",
        lambda *args, **kwargs: DummyResponse(
            {"access_token": "new-access", "expires_in": "soon"}
        ),
    )

    result = refresh_oauth_tokens(profile="default")
    assert result is not None
    assert result.expires_at == 456


def test_get_valid_access_token_refreshes(
    config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tokens = AuthTokens(access_token="expired-token", expires_at=0)
    set_oauth_tokens(profile="default", tokens=tokens)

    refreshed = AuthTokens(access_token="refreshed-token", expires_at=123)
    monkeypatch.setattr(
        refresh_module, "refresh_oauth_tokens", lambda *args, **kwargs: refreshed
    )

    result = get_valid_access_token(profile="default")
    assert result == "refreshed-token"
