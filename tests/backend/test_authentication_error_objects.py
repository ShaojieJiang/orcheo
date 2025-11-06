"""Authentication and authorization error helper tests."""

from __future__ import annotations
from orcheo_backend.app.authentication import AuthenticationError, AuthorizationError


def test_authentication_error_as_http_exception() -> None:
    """as_http_exception converts to HTTPException."""

    error = AuthenticationError(
        "Test error",
        code="test.error",
        status_code=401,
    )

    exception = error.as_http_exception()

    assert exception.status_code == 401
    assert exception.detail["code"] == "test.error"
    assert exception.detail["message"] == "Test error"
    assert "WWW-Authenticate" in exception.headers


def test_authorization_error_defaults() -> None:
    """AuthorizationError has correct default values when instantiated properly."""

    error = AuthorizationError(
        message="Forbidden",
        code="auth.forbidden",
        status_code=403,
        websocket_code=4403,
    )

    assert error.status_code == 403
    assert error.websocket_code == 4403
    assert error.code == "auth.forbidden"
