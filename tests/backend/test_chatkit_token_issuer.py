"""Tests for ChatKit token issuer caching helpers."""

from __future__ import annotations
from unittest.mock import patch
from orcheo_backend.app.chatkit_tokens import (
    get_chatkit_token_issuer,
    reset_chatkit_token_state,
)


def test_get_chatkit_token_issuer_returns_cached() -> None:
    """get_chatkit_token_issuer returns cached issuer on subsequent calls."""
    mock_settings = {"CHATKIT_TOKEN_SIGNING_KEY": "test-key"}

    with patch(
        "orcheo_backend.app.chatkit_tokens.get_settings", return_value=mock_settings
    ):
        reset_chatkit_token_state()
        issuer1 = get_chatkit_token_issuer()
        issuer2 = get_chatkit_token_issuer()

    assert issuer1 is issuer2


def test_get_chatkit_token_issuer_refresh() -> None:
    """get_chatkit_token_issuer creates new issuer when refresh=True."""
    mock_settings = {"CHATKIT_TOKEN_SIGNING_KEY": "test-key"}

    with patch(
        "orcheo_backend.app.chatkit_tokens.get_settings", return_value=mock_settings
    ):
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
        issuer1 = get_chatkit_token_issuer()
        reset_chatkit_token_state()
        issuer2 = get_chatkit_token_issuer()

    assert issuer1 is not issuer2
