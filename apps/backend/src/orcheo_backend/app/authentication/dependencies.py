from __future__ import annotations
from datetime import UTC, datetime
from sys import modules
from typing import Any
from fastapi import Request, WebSocket
from orcheo.config import get_settings
from .authenticator import Authenticator
from .context import RequestContext
from .errors import AuthenticationError
from .rate_limit import AuthRateLimiter
from .service_tokens import ServiceTokenManager
from .settings import load_auth_settings
from .telemetry import auth_telemetry


_authenticator_cache: dict[str, Authenticator | None] = {"authenticator": None}
_auth_rate_limiter_cache: dict[str, AuthRateLimiter | None] = {"limiter": None}
_token_manager_cache: dict[str, ServiceTokenManager | None] = {"manager": None}


def get_authenticator(*, refresh: bool = False) -> Authenticator:
    """Return a cached Authenticator instance, reloading settings when required."""
    if refresh:
        _authenticator_cache["authenticator"] = None
        _auth_rate_limiter_cache["limiter"] = None
        _token_manager_cache["manager"] = None
    authenticator = _authenticator_cache.get("authenticator")
    if authenticator is None:
        settings = load_auth_settings(refresh=refresh)

        from orcheo_backend.app.service_token_repository import (
            InMemoryServiceTokenRepository,
            SqliteServiceTokenRepository,
        )

        if settings.service_token_db_path:
            repository: Any = SqliteServiceTokenRepository(
                settings.service_token_db_path
            )
        else:
            repository = InMemoryServiceTokenRepository()

        token_manager = ServiceTokenManager(repository)
        _token_manager_cache["manager"] = token_manager

        authenticator = Authenticator(settings, token_manager)
        _authenticator_cache["authenticator"] = authenticator
        _auth_rate_limiter_cache["limiter"] = AuthRateLimiter(
            ip_limit=settings.rate_limit_ip,
            identity_limit=settings.rate_limit_identity,
            interval_seconds=settings.rate_limit_interval,
        )
    return authenticator


def get_service_token_manager(*, refresh: bool = False) -> ServiceTokenManager:
    """Return the cached ServiceTokenManager instance."""
    if refresh:
        _token_manager_cache["manager"] = None
    api = modules["orcheo_backend.app.authentication"]
    api.get_authenticator(refresh=refresh)
    manager = _token_manager_cache.get("manager")
    if manager is None:
        raise RuntimeError("ServiceTokenManager not initialized")
    return manager


def get_auth_rate_limiter(*, refresh: bool = False) -> AuthRateLimiter:
    """Return the configured authentication rate limiter."""
    if refresh:
        _auth_rate_limiter_cache["limiter"] = None
    limiter = _auth_rate_limiter_cache.get("limiter")
    if limiter is None:
        settings = load_auth_settings(refresh=refresh)
        limiter = AuthRateLimiter(
            ip_limit=settings.rate_limit_ip,
            identity_limit=settings.rate_limit_identity,
            interval_seconds=settings.rate_limit_interval,
        )
        _auth_rate_limiter_cache["limiter"] = limiter
    return limiter


def reset_authentication_state() -> None:
    """Clear cached authentication state and refresh Dynaconf settings."""
    _authenticator_cache["authenticator"] = None
    _auth_rate_limiter_cache["limiter"] = None
    get_settings(refresh=True)


def _extract_bearer_token(header_value: str | None) -> str:
    if not header_value:
        raise AuthenticationError("Missing bearer token", code="auth.missing_token")
    parts = header_value.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError(
            "Authorization header must use the Bearer scheme",
            code="auth.invalid_scheme",
        )
    token = parts[1].strip()
    if not token:
        raise AuthenticationError("Missing bearer token", code="auth.missing_token")
    return token


async def authenticate_request(request: Request) -> RequestContext:
    """FastAPI dependency that enforces authentication on HTTP requests."""
    api = modules["orcheo_backend.app.authentication"]
    authenticator = api.get_authenticator()
    if not authenticator.settings.enforce:
        context = RequestContext.anonymous()
        request.state.auth = context
        return context

    limiter = api.get_auth_rate_limiter()
    ip = request.client.host if request.client else None
    now = datetime.now(tz=UTC)
    try:
        limiter.check_ip(ip, now=now)
    except AuthenticationError as exc:
        raise exc.as_http_exception() from exc

    try:
        token = _extract_bearer_token(request.headers.get("Authorization"))
        context = await authenticator.authenticate(token)
    except AuthenticationError as exc:
        auth_telemetry.record_auth_failure(reason=exc.code, ip=ip)
        raise exc.as_http_exception() from exc

    try:
        limiter.check_identity(context.token_id or context.subject, now=now)
    except AuthenticationError as exc:
        raise exc.as_http_exception() from exc
    auth_telemetry.record_auth_success(context, ip=ip)
    request.state.auth = context
    return context


async def authenticate_websocket(websocket: WebSocket) -> RequestContext:
    """Authenticate a WebSocket connection before accepting it."""
    api = modules["orcheo_backend.app.authentication"]
    authenticator = api.get_authenticator()
    if not authenticator.settings.enforce:
        context = RequestContext.anonymous()
        websocket.state.auth = context
        return context

    limiter = api.get_auth_rate_limiter()
    ip = websocket.client.host if websocket.client else None
    now = datetime.now(tz=UTC)
    try:
        limiter.check_ip(ip, now=now)
    except AuthenticationError as exc:
        auth_telemetry.record_auth_failure(reason=exc.code, ip=ip)
        await websocket.close(code=exc.websocket_code, reason=exc.message)
        raise

    header_value = websocket.headers.get("authorization")
    token: str | None = None
    try:
        if header_value:
            token = _extract_bearer_token(header_value)
        else:
            query_params = websocket.query_params
            token_param = query_params.get("token") or query_params.get("access_token")
            if token_param:
                token = token_param
    except AuthenticationError as exc:
        auth_telemetry.record_auth_failure(reason=exc.code, ip=ip)
        await websocket.close(code=exc.websocket_code, reason=exc.message)
        raise

    if not token:
        auth_telemetry.record_auth_failure(reason="auth.missing_token", ip=ip)
        await websocket.close(code=4401, reason="Missing bearer token")
        raise AuthenticationError("Missing bearer token", code="auth.missing_token")

    try:
        context = await authenticator.authenticate(token)
    except AuthenticationError as exc:
        auth_telemetry.record_auth_failure(reason=exc.code, ip=ip)
        await websocket.close(code=exc.websocket_code, reason=exc.message)
        raise

    try:
        limiter.check_identity(context.token_id or context.subject, now=now)
    except AuthenticationError as exc:
        auth_telemetry.record_auth_failure(reason=exc.code, ip=ip)
        await websocket.close(code=exc.websocket_code, reason=exc.message)
        raise
    auth_telemetry.record_auth_success(context, ip=ip)
    websocket.state.auth = context
    return context


async def get_request_context(request: Request) -> RequestContext:
    """Retrieve the RequestContext associated with the current request."""
    context = getattr(request.state, "auth", None)
    if isinstance(context, RequestContext):
        return context
    return await authenticate_request(request)
