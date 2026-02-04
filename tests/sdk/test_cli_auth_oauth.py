"""OAuth flow tests for the CLI."""

from __future__ import annotations
import base64
import hashlib
import io
import urllib.parse
from collections.abc import Callable
from typing import Any
import httpx
import pytest
import orcheo_sdk.cli.auth.oauth as oauth_module
from orcheo_sdk.cli.auth.config import OAuthConfig
from orcheo_sdk.cli.auth.oauth import (
    OidcDiscovery,
    _base64_url_encode,
    _CallbackHandler,
    _create_code_challenge,
    _create_random_string,
    _exchange_code,
    _load_discovery,
    _parse_jwt_expiry,
    start_oauth_login,
)
from orcheo_sdk.cli.auth.tokens import AuthTokens
from orcheo_sdk.cli.errors import CLIError


class DummyConsole:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def print(self, message: str, *_: Any, **__: Any) -> None:
        self.messages.append(str(message))


class FakeServer:
    def __init__(self, on_handle: Callable[[], None]) -> None:
        self._on_handle = on_handle
        self.timeout: float | None = None

    def __enter__(self) -> FakeServer:
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def handle_request(self) -> None:
        self._on_handle()


class DummyResponse:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._data


def _reset_callback_handler_state() -> None:
    _CallbackHandler.authorization_code = None
    _CallbackHandler.callback_state = None
    _CallbackHandler.error = None


def _set_callback_handler_state(
    *,
    authorization_code: str | None = None,
    callback_state: str | None = None,
    error: str | None = None,
) -> None:
    _CallbackHandler.authorization_code = authorization_code
    _CallbackHandler.callback_state = callback_state
    _CallbackHandler.error = error


def _random_string_sequence(values: list[str]) -> Callable[[int], str]:
    iterator = iter(values)

    def _next(_: int) -> str:
        return next(iterator)

    return _next


def _time_sequence(values: list[float]) -> Callable[[], float]:
    iterator = iter(values)
    last = values[-1]

    def _next() -> float:
        nonlocal last
        try:
            last = next(iterator)
        except StopIteration:
            pass
        return last

    return _next


def _build_callback_handler(path: str) -> tuple[_CallbackHandler, dict[str, Any]]:
    handler = _CallbackHandler.__new__(_CallbackHandler)
    handler.path = path
    handler.wfile = io.BytesIO()
    record: dict[str, Any] = {"headers": []}

    def send_response(code: int) -> None:
        record["status"] = code

    def send_header(name: str, value: str) -> None:
        record["headers"].append((name, value))

    def end_headers() -> None:
        record["ended"] = True

    handler.send_response = send_response
    handler.send_header = send_header
    handler.end_headers = end_headers
    return handler, record


def test_base64_url_encode_no_padding() -> None:
    # Standard base64 would add padding, base64url should not
    data = b"test"
    result = _base64_url_encode(data)
    assert "=" not in result
    assert result == "dGVzdA"


def test_base64_url_encode_url_safe_chars() -> None:
    # Include bytes that would produce + or / in standard base64
    data = b"\xfb\xff"
    result = _base64_url_encode(data)
    assert "+" not in result
    assert "/" not in result
    # Should use - and _ instead
    assert "-" in result or "_" in result


def test_create_random_string_length() -> None:
    result = _create_random_string(32)
    # Base64 encoding increases length by ~4/3
    assert len(result) >= 32


def test_create_random_string_unique() -> None:
    result1 = _create_random_string(32)
    result2 = _create_random_string(32)
    assert result1 != result2


def test_create_code_challenge_s256() -> None:
    verifier = "test-verifier"
    challenge = _create_code_challenge(verifier)

    # Verify it's the SHA256 of the verifier, base64url encoded
    expected_digest = hashlib.sha256(verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(expected_digest).rstrip(b"=").decode("ascii")
    assert challenge == expected


def test_parse_jwt_expiry_valid() -> None:
    # Create a minimal JWT with exp claim
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(b'{"exp":1700000000}').rstrip(b"=").decode()
    signature = "signature"
    token = f"{header}.{payload}.{signature}"

    result = _parse_jwt_expiry(token)
    assert result == 1700000000 * 1000  # Converted to milliseconds


def test_parse_jwt_expiry_no_exp() -> None:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(b'{"sub":"user123"}').rstrip(b"=").decode()
    signature = "signature"
    token = f"{header}.{payload}.{signature}"

    result = _parse_jwt_expiry(token)
    assert result is None


def test_parse_jwt_expiry_invalid_token() -> None:
    result = _parse_jwt_expiry("not-a-jwt")
    assert result is None


def test_parse_jwt_expiry_invalid_payload() -> None:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(b"not-json").rstrip(b"=").decode()
    signature = "signature"
    token = f"{header}.{payload}.{signature}"

    result = _parse_jwt_expiry(token)
    assert result is None


def test_parse_jwt_expiry_empty_string() -> None:
    result = _parse_jwt_expiry("")
    assert result is None


def test_load_discovery_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    data = {
        "authorization_endpoint": "https://auth.example.com/authorize",
        "token_endpoint": "https://auth.example.com/token",
        "end_session_endpoint": "https://auth.example.com/logout",
    }

    def fake_get(url: str, timeout: float) -> DummyResponse:
        captured["url"] = url
        captured["timeout"] = timeout
        return DummyResponse(data)

    monkeypatch.setattr(oauth_module.httpx, "get", fake_get)

    discovery = _load_discovery("https://auth.example.com/")
    assert captured["url"] == (
        "https://auth.example.com/.well-known/openid-configuration"
    )
    assert captured["timeout"] == 30.0
    assert discovery.authorization_endpoint == data["authorization_endpoint"]
    assert discovery.token_endpoint == data["token_endpoint"]
    assert discovery.end_session_endpoint == data["end_session_endpoint"]


def test_load_discovery_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(*_: Any, **__: Any) -> None:
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(oauth_module.httpx, "get", fake_get)

    with pytest.raises(CLIError, match="Failed to load OAuth discovery"):
        _load_discovery("https://auth.example.com")


def test_callback_handler_error_response_sets_error() -> None:
    _reset_callback_handler_state()
    handler, record = _build_callback_handler("/callback?error=access_denied")

    handler.do_GET()

    assert _CallbackHandler.error == "access_denied"
    assert record["status"] == 200
    assert ("Content-Type", "text/html") in record["headers"]
    assert b"Authentication failed" in handler.wfile.getvalue()


def test_callback_handler_success_response_sets_code() -> None:
    _reset_callback_handler_state()
    handler, record = _build_callback_handler("/callback?code=auth&state=abc123")

    handler.do_GET()

    assert _CallbackHandler.authorization_code == "auth"
    assert _CallbackHandler.callback_state == "abc123"
    assert record["status"] == 200
    assert b"Authentication successful" in handler.wfile.getvalue()


def test_callback_handler_missing_params_response() -> None:
    _reset_callback_handler_state()
    handler, record = _build_callback_handler("/callback?code=auth")

    handler.do_GET()

    assert _CallbackHandler.authorization_code is None
    assert _CallbackHandler.callback_state is None
    assert record["status"] == 200
    assert b"Invalid callback" in handler.wfile.getvalue()


def test_start_oauth_login_no_browser_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console = DummyConsole()
    config = OAuthConfig(
        issuer="https://issuer.example.com",
        client_id="client-123",
        scopes="openid profile",
        audience="https://api.example.com",
        organization="org-1",
    )
    discovery = OidcDiscovery(
        authorization_endpoint="https://auth.example.com/authorize",
        token_endpoint="https://auth.example.com/token",
    )

    monkeypatch.setattr(oauth_module, "get_oauth_config", lambda **_: config)
    monkeypatch.setattr(oauth_module, "_load_discovery", lambda _: discovery)
    monkeypatch.setattr(
        oauth_module,
        "_create_random_string",
        _random_string_sequence(["state-123", "verifier-456"]),
    )
    monkeypatch.setattr(oauth_module, "_create_code_challenge", lambda _: "challenge")
    monkeypatch.setattr(
        oauth_module.socketserver,
        "TCPServer",
        lambda *_: FakeServer(
            lambda: _set_callback_handler_state(
                authorization_code="auth-code",
                callback_state="state-123",
            )
        ),
    )
    monkeypatch.setattr(oauth_module.time, "time", lambda: 1000.0)
    monkeypatch.setattr(
        oauth_module.webbrowser,
        "open",
        lambda *_: pytest.fail("webbrowser.open should not be called"),
    )

    exchange_calls: dict[str, Any] = {}

    def fake_exchange_code(
        *,
        config: OAuthConfig,
        discovery: OidcDiscovery,
        code: str,
        verifier: str,
        redirect_uri: str,
    ) -> AuthTokens:
        exchange_calls.update(
            {
                "config": config,
                "discovery": discovery,
                "code": code,
                "verifier": verifier,
                "redirect_uri": redirect_uri,
            }
        )
        return AuthTokens(access_token="access", expires_at=123)

    monkeypatch.setattr(oauth_module, "_exchange_code", fake_exchange_code)

    stored: dict[str, Any] = {}

    def fake_set_tokens(*, profile: str | None, tokens: AuthTokens) -> None:
        stored["profile"] = profile
        stored["tokens"] = tokens

    monkeypatch.setattr(oauth_module, "set_oauth_tokens", fake_set_tokens)

    start_oauth_login(console=console, profile="default", no_browser=True, port=9999)

    assert stored["profile"] == "default"
    assert stored["tokens"].access_token == "access"
    assert exchange_calls["code"] == "auth-code"
    assert exchange_calls["verifier"] == "verifier-456"
    assert exchange_calls["redirect_uri"] == "http://localhost:9999/callback"

    auth_message = next(
        msg for msg in console.messages if "Open this URL in your browser" in msg
    )
    auth_url = auth_message.split("[cyan]")[1].split("[/cyan]")[0]
    params = urllib.parse.parse_qs(urllib.parse.urlparse(auth_url).query)
    assert params["audience"] == [config.audience]
    assert params["organization"] == [config.organization]


def test_start_oauth_login_error(monkeypatch: pytest.MonkeyPatch) -> None:
    console = DummyConsole()
    config = OAuthConfig(
        issuer="https://issuer.example.com",
        client_id="client-123",
        scopes="openid profile",
        audience="https://api.example.com",
        organization="org-1",
    )
    discovery = OidcDiscovery(
        authorization_endpoint="https://auth.example.com/authorize",
        token_endpoint="https://auth.example.com/token",
    )

    monkeypatch.setattr(oauth_module, "get_oauth_config", lambda **_: config)
    monkeypatch.setattr(oauth_module, "_load_discovery", lambda _: discovery)
    monkeypatch.setattr(
        oauth_module,
        "_create_random_string",
        _random_string_sequence(["state-err", "verifier-err"]),
    )
    monkeypatch.setattr(oauth_module, "_create_code_challenge", lambda _: "challenge")
    monkeypatch.setattr(
        oauth_module.socketserver,
        "TCPServer",
        lambda *_: FakeServer(
            lambda: _set_callback_handler_state(error="access_denied")
        ),
    )
    monkeypatch.setattr(oauth_module.time, "time", lambda: 1000.0)
    monkeypatch.setattr(
        oauth_module,
        "_exchange_code",
        lambda **_: pytest.fail("exchange should not be called"),
    )

    with pytest.raises(CLIError, match="OAuth error: access_denied"):
        start_oauth_login(console=console, profile=None, no_browser=True, port=9999)


def test_start_oauth_login_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    console = DummyConsole()
    config = OAuthConfig(
        issuer="https://issuer.example.com",
        client_id="client-123",
        scopes="openid profile",
        audience="https://api.example.com",
        organization="org-1",
    )
    discovery = OidcDiscovery(
        authorization_endpoint="https://auth.example.com/authorize",
        token_endpoint="https://auth.example.com/token",
    )

    monkeypatch.setattr(oauth_module, "get_oauth_config", lambda **_: config)
    monkeypatch.setattr(oauth_module, "_load_discovery", lambda _: discovery)
    monkeypatch.setattr(
        oauth_module,
        "_create_random_string",
        _random_string_sequence(["state-timeout", "verifier-timeout"]),
    )
    monkeypatch.setattr(oauth_module, "_create_code_challenge", lambda _: "challenge")
    monkeypatch.setattr(
        oauth_module.socketserver,
        "TCPServer",
        lambda *_: FakeServer(lambda: None),
    )
    monkeypatch.setattr(
        oauth_module.time,
        "time",
        _time_sequence([0.0, 0.0, oauth_module.AUTH_STATE_TTL_SECONDS + 1.0]),
    )
    monkeypatch.setattr(
        oauth_module,
        "_exchange_code",
        lambda **_: pytest.fail("exchange should not be called"),
    )

    with pytest.raises(CLIError, match="Authentication timed out"):
        start_oauth_login(console=console, profile=None, no_browser=True, port=9999)


def test_start_oauth_login_state_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console = DummyConsole()
    config = OAuthConfig(
        issuer="https://issuer.example.com",
        client_id="client-123",
        scopes="openid profile",
        audience="https://api.example.com",
        organization="org-1",
    )
    discovery = OidcDiscovery(
        authorization_endpoint="https://auth.example.com/authorize",
        token_endpoint="https://auth.example.com/token",
    )
    opened: dict[str, str] = {}

    monkeypatch.setattr(oauth_module, "get_oauth_config", lambda **_: config)
    monkeypatch.setattr(oauth_module, "_load_discovery", lambda _: discovery)
    monkeypatch.setattr(
        oauth_module,
        "_create_random_string",
        _random_string_sequence(["state-ok", "verifier-ok"]),
    )
    monkeypatch.setattr(oauth_module, "_create_code_challenge", lambda _: "challenge")
    monkeypatch.setattr(
        oauth_module.socketserver,
        "TCPServer",
        lambda *_: FakeServer(
            lambda: _set_callback_handler_state(
                authorization_code="auth-code",
                callback_state="state-bad",
            )
        ),
    )
    monkeypatch.setattr(oauth_module.time, "time", lambda: 1000.0)
    monkeypatch.setattr(
        oauth_module,
        "_exchange_code",
        lambda **_: pytest.fail("exchange should not be called"),
    )
    monkeypatch.setattr(
        oauth_module.webbrowser,
        "open",
        lambda url: opened.update({"url": url}),
    )

    with pytest.raises(CLIError, match="OAuth state mismatch"):
        start_oauth_login(
            console=console, profile="default", no_browser=False, port=5555
        )

    assert "url" in opened


def test_exchange_code_success_expires_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = OAuthConfig(
        issuer="https://issuer.example.com",
        client_id="client-123",
        scopes="openid profile",
    )
    discovery = OidcDiscovery(
        authorization_endpoint="https://auth.example.com/authorize",
        token_endpoint="https://auth.example.com/token",
    )
    captured: dict[str, Any] = {}

    def fake_post(
        url: str, data: dict[str, str], headers: dict[str, str], timeout: float
    ) -> DummyResponse:
        captured["url"] = url
        captured["data"] = data
        captured["headers"] = headers
        captured["timeout"] = timeout
        return DummyResponse(
            {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "token_type": "Bearer",
                "expires_in": 60,
            }
        )

    monkeypatch.setattr(oauth_module.httpx, "post", fake_post)
    monkeypatch.setattr(oauth_module.time, "time", lambda: 1000.0)

    tokens = _exchange_code(
        config=config,
        discovery=discovery,
        code="auth-code",
        verifier="verifier",
        redirect_uri="http://localhost:8085/callback",
    )

    assert captured["url"] == "https://auth.example.com/token"
    assert captured["data"]["code_verifier"] == "verifier"
    assert tokens.access_token == "access-token"
    assert tokens.refresh_token == "refresh-token"
    assert tokens.expires_at == int((1000.0 + 60) * 1000)


def test_exchange_code_expiry_from_id_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = OAuthConfig(
        issuer="https://issuer.example.com",
        client_id="client-123",
        scopes="openid profile",
    )
    discovery = OidcDiscovery(
        authorization_endpoint="https://auth.example.com/authorize",
        token_endpoint="https://auth.example.com/token",
    )
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(b'{"exp":1700000000}').rstrip(b"=").decode()
    id_token = f"{header}.{payload}.sig"

    monkeypatch.setattr(
        oauth_module.httpx,
        "post",
        lambda *_, **__: DummyResponse(
            {"access_token": "not-a-jwt", "id_token": id_token, "expires_in": "n/a"}
        ),
    )

    tokens = _exchange_code(
        config=config,
        discovery=discovery,
        code="auth-code",
        verifier="verifier",
        redirect_uri="http://localhost:8085/callback",
    )

    assert tokens.expires_at == 1700000000 * 1000


def test_exchange_code_missing_access_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = OAuthConfig(
        issuer="https://issuer.example.com",
        client_id="client-123",
        scopes="openid profile",
    )
    discovery = OidcDiscovery(
        authorization_endpoint="https://auth.example.com/authorize",
        token_endpoint="https://auth.example.com/token",
    )
    monkeypatch.setattr(
        oauth_module.httpx,
        "post",
        lambda *_, **__: DummyResponse({"token_type": "Bearer"}),
    )

    with pytest.raises(CLIError, match="Token response missing access_token"):
        _exchange_code(
            config=config,
            discovery=discovery,
            code="auth-code",
            verifier="verifier",
            redirect_uri="http://localhost:8085/callback",
        )


def test_exchange_code_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    config = OAuthConfig(
        issuer="https://issuer.example.com",
        client_id="client-123",
        scopes="openid profile",
    )
    discovery = OidcDiscovery(
        authorization_endpoint="https://auth.example.com/authorize",
        token_endpoint="https://auth.example.com/token",
    )

    def fake_post(*_: Any, **__: Any) -> None:
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(oauth_module.httpx, "post", fake_post)

    with pytest.raises(CLIError, match="Token exchange failed"):
        _exchange_code(
            config=config,
            discovery=discovery,
            code="auth-code",
            verifier="verifier",
            redirect_uri="http://localhost:8085/callback",
        )
