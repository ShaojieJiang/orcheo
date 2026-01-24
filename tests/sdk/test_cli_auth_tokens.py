"""OAuth token storage tests for the CLI."""

from __future__ import annotations
import json
import time
from pathlib import Path
import pytest
from orcheo_sdk.cli.auth.tokens import (
    TOKEN_EXPIRY_SKEW_MS,
    AuthTokens,
    clear_oauth_tokens,
    get_access_token_if_valid,
    get_oauth_tokens,
    get_token_expiry_display,
    is_oauth_token_valid,
    set_oauth_tokens,
)


@pytest.fixture()
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setenv("ORCHEO_CONFIG_DIR", str(config))
    return config


def test_get_oauth_tokens_no_file(config_dir: Path) -> None:
    tokens = get_oauth_tokens(profile="default")
    assert tokens is None


def test_set_and_get_oauth_tokens(config_dir: Path) -> None:
    tokens = AuthTokens(
        access_token="access-123",
        id_token="id-456",
        refresh_token="refresh-789",
        token_type="Bearer",
        expires_at=int(time.time() * 1000) + 3600000,
    )
    set_oauth_tokens(profile="default", tokens=tokens)

    loaded = get_oauth_tokens(profile="default")
    assert loaded is not None
    assert loaded.access_token == "access-123"
    assert loaded.id_token == "id-456"
    assert loaded.refresh_token == "refresh-789"
    assert loaded.token_type == "Bearer"


def test_set_oauth_tokens_creates_directory(config_dir: Path) -> None:
    tokens = AuthTokens(access_token="access-123")
    set_oauth_tokens(profile="custom", tokens=tokens)

    tokens_dir = config_dir / "tokens"
    assert tokens_dir.exists()
    token_file = tokens_dir / "custom.json"
    assert token_file.exists()
    # Check file permissions (owner read/write only)
    assert oct(token_file.stat().st_mode)[-3:] == "600"


def test_clear_oauth_tokens(config_dir: Path) -> None:
    tokens = AuthTokens(access_token="access-123")
    set_oauth_tokens(profile="default", tokens=tokens)

    token_file = config_dir / "tokens" / "default.json"
    assert token_file.exists()

    clear_oauth_tokens(profile="default")
    assert not token_file.exists()


def test_clear_oauth_tokens_no_file(config_dir: Path) -> None:
    # Should not raise
    clear_oauth_tokens(profile="nonexistent")


def test_get_oauth_tokens_invalid_json(config_dir: Path) -> None:
    tokens_dir = config_dir / "tokens"
    tokens_dir.mkdir()
    token_file = tokens_dir / "default.json"
    token_file.write_text("invalid json", encoding="utf-8")

    tokens = get_oauth_tokens(profile="default")
    assert tokens is None


def test_get_oauth_tokens_missing_access_token(config_dir: Path) -> None:
    tokens_dir = config_dir / "tokens"
    tokens_dir.mkdir()
    token_file = tokens_dir / "default.json"
    token_file.write_text(json.dumps({"id_token": "xyz"}), encoding="utf-8")

    tokens = get_oauth_tokens(profile="default")
    assert tokens is None


def test_is_oauth_token_valid_none() -> None:
    assert not is_oauth_token_valid(None)


def test_is_oauth_token_valid_no_access_token() -> None:
    tokens = AuthTokens(access_token="")
    assert not is_oauth_token_valid(tokens)


def test_is_oauth_token_valid_no_expiry() -> None:
    tokens = AuthTokens(access_token="access-123", expires_at=None)
    assert is_oauth_token_valid(tokens)


def test_is_oauth_token_valid_not_expired() -> None:
    future = int(time.time() * 1000) + 3600000  # 1 hour from now
    tokens = AuthTokens(access_token="access-123", expires_at=future)
    assert is_oauth_token_valid(tokens)


def test_is_oauth_token_valid_expired() -> None:
    past = int(time.time() * 1000) - 3600000  # 1 hour ago
    tokens = AuthTokens(access_token="access-123", expires_at=past)
    assert not is_oauth_token_valid(tokens)


def test_is_oauth_token_valid_within_skew() -> None:
    # Expires in 30 seconds, but skew is 60 seconds, so considered expired
    almost_expired = int(time.time() * 1000) + 30000
    tokens = AuthTokens(access_token="access-123", expires_at=almost_expired)
    assert not is_oauth_token_valid(tokens)


def test_is_oauth_token_valid_just_outside_skew() -> None:
    # Expires in 90 seconds, skew is 60 seconds, so still valid
    expires_at = int(time.time() * 1000) + TOKEN_EXPIRY_SKEW_MS + 30000
    tokens = AuthTokens(access_token="access-123", expires_at=expires_at)
    assert is_oauth_token_valid(tokens)


def test_get_access_token_if_valid_returns_token(config_dir: Path) -> None:
    future = int(time.time() * 1000) + 3600000
    tokens = AuthTokens(access_token="valid-token", expires_at=future)
    set_oauth_tokens(profile="default", tokens=tokens)

    result = get_access_token_if_valid(profile="default")
    assert result == "valid-token"


def test_get_access_token_if_valid_returns_none_expired(config_dir: Path) -> None:
    past = int(time.time() * 1000) - 3600000
    tokens = AuthTokens(access_token="expired-token", expires_at=past)
    set_oauth_tokens(profile="default", tokens=tokens)

    result = get_access_token_if_valid(profile="default")
    assert result is None


def test_get_token_expiry_display_never() -> None:
    tokens = AuthTokens(access_token="abc", expires_at=None)
    assert get_token_expiry_display(tokens) == "Never"


def test_get_token_expiry_display_expired() -> None:
    past = int(time.time() * 1000) - 3600000
    tokens = AuthTokens(access_token="abc", expires_at=past)
    assert "Expired" in get_token_expiry_display(tokens)


def test_get_token_expiry_display_days() -> None:
    future = int(time.time() * 1000) + (3 * 24 * 3600 * 1000)  # 3 days
    tokens = AuthTokens(access_token="abc", expires_at=future)
    display = get_token_expiry_display(tokens)
    assert "days" in display


def test_get_token_expiry_display_hours() -> None:
    future = int(time.time() * 1000) + (5 * 3600 * 1000)  # 5 hours
    tokens = AuthTokens(access_token="abc", expires_at=future)
    display = get_token_expiry_display(tokens)
    assert "h" in display


def test_get_token_expiry_display_minutes() -> None:
    future = int(time.time() * 1000) + (30 * 60 * 1000)  # 30 minutes
    tokens = AuthTokens(access_token="abc", expires_at=future)
    display = get_token_expiry_display(tokens)
    assert "m" in display
