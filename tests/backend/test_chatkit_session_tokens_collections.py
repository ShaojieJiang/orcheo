"""Collection-related ChatKit session token tests."""

from __future__ import annotations
import jwt
import pytest
from orcheo_backend.app.chatkit_tokens import (
    ChatKitSessionTokenIssuer,
    ChatKitTokenSettings,
)


@pytest.fixture
def issuer() -> ChatKitSessionTokenIssuer:
    """Issuer fixture with deterministic configuration."""
    settings = ChatKitTokenSettings(
        signing_key="test-key",
        issuer="test-issuer",
        audience="test-audience",
        ttl_seconds=300,
    )
    return ChatKitSessionTokenIssuer(settings)


def decode_claims(token: str) -> dict:
    """Decode helper with relaxed signature verification."""
    return jwt.decode(
        token,
        "test-key",
        algorithms=["HS256"],
        options={"verify_signature": False},
    )


def test_mint_session_deduplicates_workspace_ids(
    issuer: ChatKitSessionTokenIssuer,
) -> None:
    """mint_session deduplicates and sorts workspace IDs."""
    token, _ = issuer.mint_session(
        subject="user-123",
        identity_type="human",
        token_id="token-456",
        workspace_ids=["ws-2", "ws-1", "ws-2", "ws-3"],
        primary_workspace_id="ws-1",
        workflow_id=None,
        scopes=[],
        metadata=None,
        user=None,
        assistant=None,
    )

    decoded = decode_claims(token)
    assert decoded["chatkit"]["workspace_ids"] == ["ws-1", "ws-2", "ws-3"]


def test_mint_session_deduplicates_scopes(
    issuer: ChatKitSessionTokenIssuer,
) -> None:
    """mint_session deduplicates and sorts scopes."""
    token, _ = issuer.mint_session(
        subject="user-123",
        identity_type="human",
        token_id="token-456",
        workspace_ids=None,
        primary_workspace_id=None,
        workflow_id=None,
        scopes=["write", "read", "write", "admin"],
        metadata=None,
        user=None,
        assistant=None,
    )

    decoded = decode_claims(token)
    assert decoded["chatkit"]["scopes"] == ["admin", "read", "write"]


def test_mint_session_filters_empty_workspace_ids(
    issuer: ChatKitSessionTokenIssuer,
) -> None:
    """mint_session filters out empty strings from workspace IDs."""
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

    decoded = decode_claims(token)
    assert decoded["chatkit"]["workspace_ids"] == ["ws-1", "ws-2"]


def test_mint_session_filters_empty_scopes(
    issuer: ChatKitSessionTokenIssuer,
) -> None:
    """mint_session filters out empty strings from scopes."""
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

    decoded = decode_claims(token)
    assert decoded["chatkit"]["scopes"] == ["read", "write"]
