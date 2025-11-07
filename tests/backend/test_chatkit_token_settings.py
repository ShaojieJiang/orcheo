"""ChatKit token settings and helper utility tests."""

from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from orcheo_backend.app.chatkit_tokens import (
    ChatKitTokenConfigurationError,
    ChatKitTokenSettings,
    _coerce_optional_str,
    _parse_int,
    load_chatkit_token_settings,
)


def test_chatkit_token_settings_creation() -> None:
    """ChatKitTokenSettings can be instantiated with explicit values."""
    settings = ChatKitTokenSettings(
        signing_key="test-key",
        issuer="test-issuer",
        audience="test-audience",
        ttl_seconds=300,
        algorithm="HS256",
    )
    assert settings.signing_key == "test-key"
    assert settings.issuer == "test-issuer"
    assert settings.audience == "test-audience"
    assert settings.ttl_seconds == 300
    assert settings.algorithm == "HS256"


def test_coerce_optional_str_with_none() -> None:
    """_coerce_optional_str returns None when given None."""
    assert _coerce_optional_str(None) is None


def test_coerce_optional_str_with_empty_string() -> None:
    """_coerce_optional_str returns None for empty or whitespace strings."""
    assert _coerce_optional_str("") is None
    assert _coerce_optional_str("   ") is None
    assert _coerce_optional_str("\t\n") is None


def test_coerce_optional_str_with_valid_string() -> None:
    """_coerce_optional_str returns stripped string for valid input."""
    assert _coerce_optional_str("hello") == "hello"
    assert _coerce_optional_str("  hello  ") == "hello"


def test_parse_int_with_valid_int() -> None:
    """_parse_int returns integer value for valid input."""
    assert _parse_int(42, 100) == 42
    assert _parse_int("42", 100) == 42


def test_parse_int_with_none() -> None:
    """_parse_int returns default when given None."""
    assert _parse_int(None, 100) == 100


def test_parse_int_with_invalid_value() -> None:
    """_parse_int returns default for invalid input."""
    assert _parse_int("not-a-number", 100) == 100
    assert _parse_int("", 100) == 100


def test_load_chatkit_token_settings_with_signing_key() -> None:
    """load_chatkit_token_settings uses CHATKIT_TOKEN_SIGNING_KEY."""
    mock_settings = {
        "CHATKIT_TOKEN_SIGNING_KEY": "my-signing-key",
        "CHATKIT_TOKEN_ISSUER": "my-issuer",
        "CHATKIT_TOKEN_AUDIENCE": "my-audience",
        "CHATKIT_TOKEN_TTL_SECONDS": "600",
        "CHATKIT_TOKEN_ALGORITHM": "HS512",
    }

    with patch(
        "orcheo_backend.app.chatkit_tokens.get_settings", return_value=mock_settings
    ):
        settings = load_chatkit_token_settings()

    assert settings.signing_key == "my-signing-key"
    assert settings.issuer == "my-issuer"
    assert settings.audience == "my-audience"
    assert settings.ttl_seconds == 600
    assert settings.algorithm == "HS512"


def test_load_chatkit_token_settings_fallback_to_client_secret() -> None:
    """load_chatkit_token_settings falls back to CHATKIT_CLIENT_SECRET."""
    mock_settings = {
        "CHATKIT_CLIENT_SECRET": "client-secret-key",
    }

    with patch(
        "orcheo_backend.app.chatkit_tokens.get_settings", return_value=mock_settings
    ):
        settings = load_chatkit_token_settings()

    assert settings.signing_key == "client-secret-key"
    assert settings.issuer == "orcheo.chatkit"
    assert settings.audience == "chatkit"
    assert settings.ttl_seconds == 300
    assert settings.algorithm == "HS256"


def test_load_chatkit_token_settings_missing_key_raises_error() -> None:
    """load_chatkit_token_settings raises error when no signing key is configured."""
    mock_settings = {}

    with patch(
        "orcheo_backend.app.chatkit_tokens.get_settings", return_value=mock_settings
    ):
        with pytest.raises(ChatKitTokenConfigurationError) as exc_info:
            load_chatkit_token_settings()

    assert "signing key is not configured" in str(exc_info.value)


def test_load_chatkit_token_settings_minimum_ttl() -> None:
    """load_chatkit_token_settings enforces minimum TTL of 60 seconds."""
    mock_settings = {
        "CHATKIT_TOKEN_SIGNING_KEY": "test-key",
        "CHATKIT_TOKEN_TTL_SECONDS": "30",
    }

    with patch(
        "orcheo_backend.app.chatkit_tokens.get_settings", return_value=mock_settings
    ):
        settings = load_chatkit_token_settings()

    assert settings.ttl_seconds == 60


def test_load_chatkit_token_settings_refresh_flag() -> None:
    """load_chatkit_token_settings passes refresh flag to get_settings."""
    mock_settings = {"CHATKIT_TOKEN_SIGNING_KEY": "test-key"}
    mock_get_settings = MagicMock(return_value=mock_settings)

    with patch("orcheo_backend.app.chatkit_tokens.get_settings", mock_get_settings):
        load_chatkit_token_settings(refresh=True)

    mock_get_settings.assert_called_once_with(refresh=True)
