"""Tests for ChatKit router helper utilities that don't hit persistence."""

from __future__ import annotations
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
import jwt
import pytest
from fastapi import HTTPException, status
from orcheo_backend.app.authentication import AuthenticationError
from orcheo_backend.app.chatkit_tokens import ChatKitTokenConfigurationError
from orcheo_backend.app.routers import chatkit
from tests.backend.chatkit_router_helpers_support import (
    make_chatkit_request,
)


pytestmark = pytest.mark.usefixtures("reset_chatkit_limiters")


class _HeaderProxy(str):
    """Custom header type controlling the split output for branch coverage."""

    def __new__(cls, value: str, parts: list[str]) -> _HeaderProxy:
        obj = str.__new__(cls, value)
        obj._parts = parts
        return obj

    def split(self) -> list[str]:  # type: ignore[override]
        return list(self._parts)


def test_coerce_rate_limit_returns_default_for_invalid_values() -> None:
    config = {"limit": "not-an-int"}
    assert chatkit._coerce_rate_limit(config, "limit", 25) == 25


def test_chatkit_error_includes_auth_mode() -> None:
    exc = chatkit._chatkit_error(
        status.HTTP_401_UNAUTHORIZED,
        message="boom",
        code="chatkit.auth.test",
        auth_mode="jwt",
    )
    assert exc.detail["auth_mode"] == "jwt"


def test_extract_bearer_token_requires_header() -> None:
    with pytest.raises(HTTPException) as excinfo:
        chatkit._extract_bearer_token(None)
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_extract_bearer_token_requires_bearer_scheme() -> None:
    with pytest.raises(HTTPException) as excinfo:
        chatkit._extract_bearer_token("Basic token")
    assert excinfo.value.detail["code"] == "chatkit.auth.invalid_scheme"


def test_extract_bearer_token_requires_token_value() -> None:
    header = _HeaderProxy("Bearer", ["Bearer", "   "])
    with pytest.raises(HTTPException) as excinfo:
        chatkit._extract_bearer_token(header)
    assert excinfo.value.detail["code"] == "chatkit.auth.missing_token"


def test_decode_chatkit_jwt_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise() -> None:
        raise ChatKitTokenConfigurationError("missing key")

    monkeypatch.setattr(chatkit, "load_chatkit_token_settings", _raise)

    with pytest.raises(HTTPException) as excinfo:
        chatkit._decode_chatkit_jwt("token")
    assert excinfo.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_decode_chatkit_jwt_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        signing_key="secret",
        algorithm="HS256",
        audience="aud",
        issuer="iss",
    )
    monkeypatch.setattr(chatkit, "load_chatkit_token_settings", lambda: settings)

    def _raise_decode(*args: Any, **kwargs: Any) -> None:
        raise jwt.PyJWTError("bad")

    monkeypatch.setattr(chatkit.jwt, "decode", _raise_decode)  # type: ignore[attr-defined]

    with pytest.raises(HTTPException) as excinfo:
        chatkit._decode_chatkit_jwt("token")
    assert excinfo.value.detail["code"] == "chatkit.auth.invalid_jwt"


def test_decode_chatkit_jwt_success(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        signing_key="secret",
        algorithm="HS256",
        audience="aud",
        issuer="iss",
    )
    monkeypatch.setattr(chatkit, "load_chatkit_token_settings", lambda: settings)
    monkeypatch.setattr(
        chatkit.jwt,
        "decode",
        lambda *args, **kwargs: {"sub": "alice"},
    )  # type: ignore[attr-defined]

    payload = chatkit._decode_chatkit_jwt("token")
    assert payload["sub"] == "alice"


def test_extract_session_subject_uses_cookie_fallback() -> None:
    request = make_chatkit_request(cookies={"orcheo_oauth_session": "user-1"})
    assert chatkit._extract_session_subject(request) == "user-1"


def test_rate_limit_reraises_authentication_error() -> None:
    error = AuthenticationError(
        "denied",
        code="chatkit.rate",
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    )

    class DummyLimiter:
        def hit(self, key: str, *, now: datetime) -> None:
            raise error

    with pytest.raises(HTTPException) as excinfo:
        chatkit._rate_limit(DummyLimiter(), "key", now=datetime.now(tz=UTC))
    assert excinfo.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
