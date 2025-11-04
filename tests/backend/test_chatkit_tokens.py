"""Unit tests for ChatKit token minting and configuration."""

from __future__ import annotations
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID
import jwt
import pytest
from orcheo_backend.app.chatkit_tokens import (
    ChatKitSessionTokenIssuer,
    ChatKitTokenConfigurationError,
    ChatKitTokenSettings,
    _coerce_optional_str,
    _parse_int,
    get_chatkit_token_issuer,
    load_chatkit_token_settings,
    reset_chatkit_token_state,
)


def test_chatkit_token_settings_creation() -> None:
    """ChatKitTokenSettings can be created with all parameters."""
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


def test_chatkit_session_token_issuer_settings_property() -> None:
    """ChatKitSessionTokenIssuer exposes settings property."""
    settings = ChatKitTokenSettings(
        signing_key="test-key",
        issuer="test-issuer",
        audience="test-audience",
        ttl_seconds=300,
    )
    issuer = ChatKitSessionTokenIssuer(settings)
    assert issuer.settings == settings


def test_mint_session_basic() -> None:
    """mint_session creates a valid JWT with basic parameters."""
    settings = ChatKitTokenSettings(
        signing_key="test-secret-key",
        issuer="test-issuer",
        audience="test-audience",
        ttl_seconds=300,
    )
    issuer = ChatKitSessionTokenIssuer(settings)

    token, expires_at = issuer.mint_session(
        subject="user-123",
        identity_type="human",
        token_id="token-456",
        workspace_ids=["ws-1", "ws-2"],
        primary_workspace_id="ws-1",
        workflow_id=UUID("12345678-1234-1234-1234-123456789abc"),
        scopes=["read", "write"],
        metadata=None,
        user=None,
        assistant=None,
    )

    # Verify token is a valid JWT
    assert isinstance(token, str)
    assert isinstance(expires_at, datetime)

    # Decode and verify claims
    decoded = jwt.decode(
        token,
        "test-secret-key",
        algorithms=["HS256"],
        audience="test-audience",
        issuer="test-issuer",
    )

    assert decoded["sub"] == "user-123"
    assert decoded["iss"] == "test-issuer"
    assert decoded["aud"] == "test-audience"
    assert decoded["chatkit"]["identity_type"] == "human"
    assert decoded["chatkit"]["token_id"] == "token-456"
    assert decoded["chatkit"]["workspace_id"] == "ws-1"
    assert decoded["chatkit"]["workspace_ids"] == ["ws-1", "ws-2"]
    assert decoded["chatkit"]["workflow_id"] == "12345678-1234-1234-1234-123456789abc"
    assert decoded["chatkit"]["scopes"] == ["read", "write"]


def test_mint_session_with_metadata() -> None:
    """mint_session includes metadata in chatkit claims."""
    settings = ChatKitTokenSettings(
        signing_key="test-key",
        issuer="test-issuer",
        audience="test-audience",
        ttl_seconds=300,
    )
    issuer = ChatKitSessionTokenIssuer(settings)

    metadata = {"custom_field": "custom_value"}
    token, _ = issuer.mint_session(
        subject="user-123",
        identity_type="human",
        token_id="token-456",
        workspace_ids=None,
        primary_workspace_id=None,
        workflow_id=None,
        scopes=[],
        metadata=metadata,
        user=None,
        assistant=None,
    )

    decoded = jwt.decode(
        token, "test-key", algorithms=["HS256"], options={"verify_signature": False}
    )
    assert decoded["chatkit"]["metadata"] == metadata


def test_mint_session_with_user() -> None:
    """mint_session includes user information in chatkit claims."""
    settings = ChatKitTokenSettings(
        signing_key="test-key",
        issuer="test-issuer",
        audience="test-audience",
        ttl_seconds=300,
    )
    issuer = ChatKitSessionTokenIssuer(settings)

    user = {"name": "John Doe", "email": "john@example.com"}
    token, _ = issuer.mint_session(
        subject="user-123",
        identity_type="human",
        token_id="token-456",
        workspace_ids=None,
        primary_workspace_id=None,
        workflow_id=None,
        scopes=[],
        metadata=None,
        user=user,
        assistant=None,
    )

    decoded = jwt.decode(
        token, "test-key", algorithms=["HS256"], options={"verify_signature": False}
    )
    assert decoded["chatkit"]["user"] == user


def test_mint_session_with_assistant() -> None:
    """mint_session includes assistant information in chatkit claims."""
    settings = ChatKitTokenSettings(
        signing_key="test-key",
        issuer="test-issuer",
        audience="test-audience",
        ttl_seconds=300,
    )
    issuer = ChatKitSessionTokenIssuer(settings)

    assistant = {"model": "gpt-4", "provider": "openai"}
    token, _ = issuer.mint_session(
        subject="user-123",
        identity_type="human",
        token_id="token-456",
        workspace_ids=None,
        primary_workspace_id=None,
        workflow_id=None,
        scopes=[],
        metadata=None,
        user=None,
        assistant=assistant,
    )

    decoded = jwt.decode(
        token, "test-key", algorithms=["HS256"], options={"verify_signature": False}
    )
    assert decoded["chatkit"]["assistant"] == assistant


def test_mint_session_with_extra() -> None:
    """mint_session merges extra claims into chatkit claims."""
    settings = ChatKitTokenSettings(
        signing_key="test-key",
        issuer="test-issuer",
        audience="test-audience",
        ttl_seconds=300,
    )
    issuer = ChatKitSessionTokenIssuer(settings)

    extra = {"custom_claim": "custom_value", "another_claim": 42}
    token, _ = issuer.mint_session(
        subject="user-123",
        identity_type="human",
        token_id="token-456",
        workspace_ids=None,
        primary_workspace_id=None,
        workflow_id=None,
        scopes=[],
        metadata=None,
        user=None,
        assistant=None,
        extra=extra,
    )

    decoded = jwt.decode(
        token, "test-key", algorithms=["HS256"], options={"verify_signature": False}
    )
    assert decoded["chatkit"]["custom_claim"] == "custom_value"
    assert decoded["chatkit"]["another_claim"] == 42


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
        "CHATKIT_TOKEN_TTL_SECONDS": "30",  # Below minimum
    }

    with patch(
        "orcheo_backend.app.chatkit_tokens.get_settings", return_value=mock_settings
    ):
        settings = load_chatkit_token_settings()

    assert settings.ttl_seconds == 60  # Should be clamped to minimum


def test_load_chatkit_token_settings_refresh_flag() -> None:
    """load_chatkit_token_settings passes refresh flag to get_settings."""
    mock_settings = {"CHATKIT_TOKEN_SIGNING_KEY": "test-key"}
    mock_get_settings = MagicMock(return_value=mock_settings)

    with patch("orcheo_backend.app.chatkit_tokens.get_settings", mock_get_settings):
        load_chatkit_token_settings(refresh=True)

    mock_get_settings.assert_called_once_with(refresh=True)


def test_get_chatkit_token_issuer_returns_cached() -> None:
    """get_chatkit_token_issuer returns cached issuer on subsequent calls."""
    mock_settings = {"CHATKIT_TOKEN_SIGNING_KEY": "test-key"}

    with patch(
        "orcheo_backend.app.chatkit_tokens.get_settings", return_value=mock_settings
    ):
        # Clear cache first
        reset_chatkit_token_state()

        # First call creates issuer
        issuer1 = get_chatkit_token_issuer()
        # Second call returns same instance
        issuer2 = get_chatkit_token_issuer()

        assert issuer1 is issuer2


def test_get_chatkit_token_issuer_refresh() -> None:
    """get_chatkit_token_issuer creates new issuer when refresh=True."""
    mock_settings = {"CHATKIT_TOKEN_SIGNING_KEY": "test-key"}

    with patch(
        "orcheo_backend.app.chatkit_tokens.get_settings", return_value=mock_settings
    ):
        # Clear cache first
        reset_chatkit_token_state()

        issuer1 = get_chatkit_token_issuer()
        issuer2 = get_chatkit_token_issuer(refresh=True)

        assert issuer1 is not issuer2


def test_reset_chatkit_token_state() -> None:
    """reset_chatkit_token_state clears the issuer cache."""
    mock_settings = {"CHATKIT_TOKEN_SIGNING_KEY": "test-key"}

    with patch(
        "orcheo_backend.app.chatkit_tokens.get_settings", return_value=mock_settings
    ):
        # Create cached issuer
        issuer1 = get_chatkit_token_issuer()

        # Reset state
        reset_chatkit_token_state()

        # New issuer should be created
        issuer2 = get_chatkit_token_issuer()

        assert issuer1 is not issuer2


def test_mint_session_deduplicates_workspace_ids() -> None:
    """mint_session deduplicates and sorts workspace IDs."""
    settings = ChatKitTokenSettings(
        signing_key="test-key",
        issuer="test-issuer",
        audience="test-audience",
        ttl_seconds=300,
    )
    issuer = ChatKitSessionTokenIssuer(settings)

    token, _ = issuer.mint_session(
        subject="user-123",
        identity_type="human",
        token_id="token-456",
        workspace_ids=["ws-2", "ws-1", "ws-2", "ws-3"],  # Duplicates and unsorted
        primary_workspace_id="ws-1",
        workflow_id=None,
        scopes=[],
        metadata=None,
        user=None,
        assistant=None,
    )

    decoded = jwt.decode(
        token, "test-key", algorithms=["HS256"], options={"verify_signature": False}
    )
    assert decoded["chatkit"]["workspace_ids"] == ["ws-1", "ws-2", "ws-3"]


def test_mint_session_deduplicates_scopes() -> None:
    """mint_session deduplicates and sorts scopes."""
    settings = ChatKitTokenSettings(
        signing_key="test-key",
        issuer="test-issuer",
        audience="test-audience",
        ttl_seconds=300,
    )
    issuer = ChatKitSessionTokenIssuer(settings)

    token, _ = issuer.mint_session(
        subject="user-123",
        identity_type="human",
        token_id="token-456",
        workspace_ids=None,
        primary_workspace_id=None,
        workflow_id=None,
        scopes=["write", "read", "write", "admin"],  # Duplicates and unsorted
        metadata=None,
        user=None,
        assistant=None,
    )

    decoded = jwt.decode(
        token, "test-key", algorithms=["HS256"], options={"verify_signature": False}
    )
    assert decoded["chatkit"]["scopes"] == ["admin", "read", "write"]


def test_mint_session_filters_empty_workspace_ids() -> None:
    """mint_session filters out empty strings from workspace IDs."""
    settings = ChatKitTokenSettings(
        signing_key="test-key",
        issuer="test-issuer",
        audience="test-audience",
        ttl_seconds=300,
    )
    issuer = ChatKitSessionTokenIssuer(settings)

    token, _ = issuer.mint_session(
        subject="user-123",
        identity_type="human",
        token_id="token-456",
        workspace_ids=["ws-1", "", "ws-2", ""],
        primary_workspace_id="ws-1",
        workflow_id=None,
        scopes=[],
        metadata=None,
        user=None,
        assistant=None,
    )

    decoded = jwt.decode(
        token, "test-key", algorithms=["HS256"], options={"verify_signature": False}
    )
    assert decoded["chatkit"]["workspace_ids"] == ["ws-1", "ws-2"]


def test_mint_session_filters_empty_scopes() -> None:
    """mint_session filters out empty strings from scopes."""
    settings = ChatKitTokenSettings(
        signing_key="test-key",
        issuer="test-issuer",
        audience="test-audience",
        ttl_seconds=300,
    )
    issuer = ChatKitSessionTokenIssuer(settings)

    token, _ = issuer.mint_session(
        subject="user-123",
        identity_type="human",
        token_id="token-456",
        workspace_ids=None,
        primary_workspace_id=None,
        workflow_id=None,
        scopes=["read", "", "write"],
        metadata=None,
        user=None,
        assistant=None,
    )

    decoded = jwt.decode(
        token, "test-key", algorithms=["HS256"], options={"verify_signature": False}
    )
    assert decoded["chatkit"]["scopes"] == ["read", "write"]


def test_mint_session_with_none_workflow_id() -> None:
    """mint_session handles None workflow_id correctly."""
    settings = ChatKitTokenSettings(
        signing_key="test-key",
        issuer="test-issuer",
        audience="test-audience",
        ttl_seconds=300,
    )
    issuer = ChatKitSessionTokenIssuer(settings)

    token, _ = issuer.mint_session(
        subject="user-123",
        identity_type="human",
        token_id="token-456",
        workspace_ids=None,
        primary_workspace_id=None,
        workflow_id=None,
        scopes=[],
        metadata=None,
        user=None,
        assistant=None,
    )

    decoded = jwt.decode(
        token, "test-key", algorithms=["HS256"], options={"verify_signature": False}
    )
    assert decoded["chatkit"]["workflow_id"] is None


def test_mint_session_expiry_calculation() -> None:
    """mint_session calculates correct expiry time based on TTL."""
    settings = ChatKitTokenSettings(
        signing_key="test-key",
        issuer="test-issuer",
        audience="test-audience",
        ttl_seconds=600,
    )
    issuer = ChatKitSessionTokenIssuer(settings)

    before = datetime.now(tz=UTC)
    token, expires_at = issuer.mint_session(
        subject="user-123",
        identity_type="human",
        token_id="token-456",
        workspace_ids=None,
        primary_workspace_id=None,
        workflow_id=None,
        scopes=[],
        metadata=None,
        user=None,
        assistant=None,
    )
    after = datetime.now(tz=UTC)

    # Expiry should be roughly 600 seconds from now
    decoded = jwt.decode(
        token, "test-key", algorithms=["HS256"], options={"verify_signature": False}
    )
    exp_timestamp = decoded["exp"]
    iat_timestamp = decoded["iat"]

    # Verify the TTL is correct
    assert exp_timestamp - iat_timestamp == 600

    # Verify timestamps are within reasonable bounds
    assert before.timestamp() - 1 <= iat_timestamp <= after.timestamp() + 1
    assert before.timestamp() + 599 <= expires_at.timestamp() <= after.timestamp() + 601
