"""Core ChatKit session token minting tests."""

from __future__ import annotations
from datetime import UTC, datetime
from uuid import UUID
import jwt
import pytest
from orcheo_backend.app.chatkit_tokens import (
    ChatKitSessionTokenIssuer,
    ChatKitTokenSettings,
)


@pytest.fixture
def default_settings() -> ChatKitTokenSettings:
    """Convenience fixture for common settings."""
    return ChatKitTokenSettings(
        signing_key="test-key",
        issuer="test-issuer",
        audience="test-audience",
        ttl_seconds=300,
    )


def decode_payload(token: str, settings: ChatKitTokenSettings) -> dict:
    """Decode helper with relaxed signature verification."""
    return jwt.decode(
        token,
        settings.signing_key,
        algorithms=[settings.algorithm],
        options={"verify_signature": False},
    )


def test_chatkit_session_token_issuer_settings_property(
    default_settings: ChatKitTokenSettings,
) -> None:
    """ChatKitSessionTokenIssuer exposes settings property."""
    issuer = ChatKitSessionTokenIssuer(default_settings)
    assert issuer.settings == default_settings


def test_mint_session_basic(default_settings: ChatKitTokenSettings) -> None:
    """mint_session creates a valid JWT with expected claims."""
    issuer = ChatKitSessionTokenIssuer(default_settings)

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

    assert isinstance(token, str)
    assert isinstance(expires_at, datetime)

    decoded = jwt.decode(
        token,
        default_settings.signing_key,
        algorithms=[default_settings.algorithm],
        audience=default_settings.audience,
        issuer=default_settings.issuer,
    )
    assert decoded["sub"] == "user-123"
    assert decoded["chatkit"]["identity_type"] == "human"
    assert decoded["chatkit"]["token_id"] == "token-456"
    assert decoded["chatkit"]["workspace_id"] == "ws-1"
    assert decoded["chatkit"]["workspace_ids"] == ["ws-1", "ws-2"]
    assert decoded["chatkit"]["workflow_id"] == "12345678-1234-1234-1234-123456789abc"
    assert decoded["chatkit"]["scopes"] == ["read", "write"]


def test_mint_session_with_metadata(default_settings: ChatKitTokenSettings) -> None:
    """mint_session includes metadata in chatkit claims."""
    issuer = ChatKitSessionTokenIssuer(default_settings)
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

    decoded = decode_payload(token, default_settings)
    assert decoded["chatkit"]["metadata"] == metadata


def test_mint_session_with_user(default_settings: ChatKitTokenSettings) -> None:
    """mint_session includes user information in chatkit claims."""
    issuer = ChatKitSessionTokenIssuer(default_settings)
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

    decoded = decode_payload(token, default_settings)
    assert decoded["chatkit"]["user"] == user


def test_mint_session_with_assistant(default_settings: ChatKitTokenSettings) -> None:
    """mint_session includes assistant information in chatkit claims."""
    issuer = ChatKitSessionTokenIssuer(default_settings)
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

    decoded = decode_payload(token, default_settings)
    assert decoded["chatkit"]["assistant"] == assistant


def test_mint_session_with_extra(default_settings: ChatKitTokenSettings) -> None:
    """mint_session merges extra claims into chatkit claims."""
    issuer = ChatKitSessionTokenIssuer(default_settings)
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

    decoded = decode_payload(token, default_settings)
    assert decoded["chatkit"]["custom_claim"] == "custom_value"
    assert decoded["chatkit"]["another_claim"] == 42


def test_mint_session_with_none_workflow_id(
    default_settings: ChatKitTokenSettings,
) -> None:
    """mint_session handles None workflow_id correctly."""
    issuer = ChatKitSessionTokenIssuer(default_settings)

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

    decoded = decode_payload(token, default_settings)
    assert decoded["chatkit"]["workflow_id"] is None


def test_mint_session_expiry_calculation(
    default_settings: ChatKitTokenSettings,
) -> None:
    """mint_session calculates correct expiry time based on TTL."""
    custom_settings = ChatKitTokenSettings(
        signing_key=default_settings.signing_key,
        issuer=default_settings.issuer,
        audience=default_settings.audience,
        ttl_seconds=600,
    )
    issuer = ChatKitSessionTokenIssuer(custom_settings)

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

    decoded = decode_payload(token, custom_settings)
    exp_timestamp = decoded["exp"]
    iat_timestamp = decoded["iat"]

    assert exp_timestamp - iat_timestamp == 600
    assert before.timestamp() - 1 <= iat_timestamp <= after.timestamp() + 1
    assert before.timestamp() + 599 <= expires_at.timestamp() <= after.timestamp() + 601
