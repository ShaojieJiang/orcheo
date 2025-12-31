"""Cover additional branches in authentication websocket helpers."""

from __future__ import annotations
from types import SimpleNamespace
from orcheo_backend.app.authentication.dependencies import (
    _extract_websocket_protocol_token,
    _resolve_websocket_token,
)


def test_extract_websocket_protocol_token_returns_none_for_blank_header() -> None:
    """Empty or whitespace-only headers do not yield tokens or subprotocols."""

    assert _extract_websocket_protocol_token(None) == (None, None)
    assert _extract_websocket_protocol_token(" ,,   ") == (None, None)


def test_extract_websocket_protocol_token_finds_bearer_token_and_subprotocol() -> None:
    """Token parsing ignores empty bearer entries and reports the
    orcheo-auth subprotocol.
    """

    header = "foo, orcheo-auth, bearer., bearer.valid-token, bar"
    token, subprotocol = _extract_websocket_protocol_token(header)

    assert token == "valid-token"
    assert subprotocol == "orcheo-auth"


def test_resolve_websocket_token_prefers_authorization_header() -> None:
    """An explicit Authorization header takes precedence over websocket
    protocols.
    """

    headers = {
        "sec-websocket-protocol": "orcheo-auth",
        "authorization": "Bearer auth-header-token",
    }
    websocket = SimpleNamespace(headers=headers)

    token, subprotocol = _resolve_websocket_token(websocket)
    assert token == "auth-header-token"
    assert subprotocol == "orcheo-auth"


def test_resolve_websocket_token_uses_protocol_token_without_authorization() -> None:
    """Fall back to the protocol bearer token on Authorization header absent."""

    headers = {"sec-websocket-protocol": "bearer.protocol-token"}
    websocket = SimpleNamespace(headers=headers)

    token, subprotocol = _resolve_websocket_token(websocket)
    assert token == "protocol-token"
    assert subprotocol is None
