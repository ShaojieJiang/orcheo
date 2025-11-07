"""WebSocket authentication tests split from the extended suite."""

from __future__ import annotations
from unittest.mock import AsyncMock, Mock, patch
import pytest
from starlette.websockets import WebSocket
from orcheo_backend.app.authentication import (
    AuthenticationError,
    AuthSettings,
    authenticate_websocket,
    reset_authentication_state,
)
from tests.backend.authentication_test_utils import (
    _setup_service_token,
    reset_auth_state,
)


@pytest.fixture(autouse=True)
def _reset_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure authentication state is cleared between tests."""

    yield from reset_auth_state(monkeypatch)


@pytest.mark.asyncio
async def test_authenticate_websocket_with_auth_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WebSocket authentication via Authorization header."""

    token = "ws-token"
    _setup_service_token(monkeypatch, token, identifier="ws")
    reset_authentication_state()

    websocket = Mock(spec=WebSocket)
    websocket.headers = {"authorization": f"Bearer {token}"}
    websocket.query_params = {}
    websocket.client = Mock(host="1.2.3.4")
    websocket.state = Mock()

    context = await authenticate_websocket(websocket)

    assert context.is_authenticated
    assert context.identity_type == "service"


@pytest.mark.asyncio
async def test_authenticate_websocket_with_query_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WebSocket authentication via query parameter."""

    token = "ws-query-token"
    _setup_service_token(monkeypatch, token, identifier="ws-query")
    reset_authentication_state()

    websocket = Mock(spec=WebSocket)
    websocket.headers = {}
    websocket.query_params = {"token": token}
    websocket.client = Mock(host="1.2.3.4")
    websocket.state = Mock()

    context = await authenticate_websocket(websocket)

    assert context.is_authenticated


@pytest.mark.asyncio
async def test_authenticate_websocket_with_access_token_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WebSocket authentication via access_token query parameter."""

    token = "ws-access-token"
    _setup_service_token(monkeypatch, token, identifier="ws-access")
    reset_authentication_state()

    websocket = Mock(spec=WebSocket)
    websocket.headers = {}
    websocket.query_params = {"access_token": token}
    websocket.client = Mock(host="1.2.3.4")
    websocket.state = Mock()
    websocket.close = AsyncMock()

    context = await authenticate_websocket(websocket)

    assert context.is_authenticated


@pytest.mark.asyncio
async def test_authenticate_websocket_missing_token() -> None:
    """WebSocket authentication fails when no token provided."""

    # Force authentication requirement
    with patch("orcheo_backend.app.authentication.get_authenticator") as mock_auth:
        mock_settings = AuthSettings(
            mode="required",
            jwt_secret=None,
            jwks_url=None,
            jwks_static=(),
            jwks_cache_ttl=300,
            jwks_timeout=5.0,
            allowed_algorithms=(),
            audiences=(),
            issuer=None,
            service_token_db_path=None,
            rate_limit_ip=0,
            rate_limit_identity=0,
            rate_limit_interval=60,
        )
        mock_authenticator = Mock()
        mock_authenticator.settings = mock_settings
        mock_auth.return_value = mock_authenticator

        websocket = Mock(spec=WebSocket)
        websocket.headers = {}
        websocket.query_params = {}
        websocket.client = Mock(host="1.2.3.4")
        websocket.state = Mock()
        websocket.close = AsyncMock()

        with patch("orcheo_backend.app.authentication.get_auth_rate_limiter"):
            with pytest.raises(AuthenticationError):
                await authenticate_websocket(websocket)

        websocket.close.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_websocket_invalid_scheme() -> None:
    """WebSocket authentication fails with invalid Authorization scheme."""

    with patch("orcheo_backend.app.authentication.get_authenticator") as mock_auth:
        mock_settings = AuthSettings(
            mode="required",
            jwt_secret=None,
            jwks_url=None,
            jwks_static=(),
            jwks_cache_ttl=300,
            jwks_timeout=5.0,
            allowed_algorithms=(),
            audiences=(),
            issuer=None,
            service_token_db_path=None,
            rate_limit_ip=0,
            rate_limit_identity=0,
            rate_limit_interval=60,
        )
        mock_authenticator = Mock()
        mock_authenticator.settings = mock_settings
        mock_auth.return_value = mock_authenticator

        websocket = Mock(spec=WebSocket)
        websocket.headers = {"authorization": "Basic dXNlcjpwYXNz"}
        websocket.query_params = {}
        websocket.client = Mock(host="1.2.3.4")
        websocket.state = Mock()
        websocket.close = AsyncMock()

        with patch("orcheo_backend.app.authentication.get_auth_rate_limiter"):
            with pytest.raises(AuthenticationError):
                await authenticate_websocket(websocket)

        websocket.close.assert_called_once()


# Helper function tests


@pytest.mark.asyncio
async def test_authenticate_websocket_anonymous_when_disabled() -> None:
    """WebSocket authentication allows anonymous when disabled."""

    websocket = Mock(spec=WebSocket)
    websocket.headers = {}
    websocket.query_params = {}
    websocket.client = Mock(host="1.2.3.4")
    websocket.state = Mock()

    context = await authenticate_websocket(websocket)

    assert not context.is_authenticated
    assert context.identity_type == "anonymous"
