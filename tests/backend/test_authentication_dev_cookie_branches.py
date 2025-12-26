"""Cover missing branches in dependencies: dev cookie and default scopes."""

from __future__ import annotations
from starlette.requests import Request
from orcheo_backend.app.authentication.dependencies import (
    _build_dev_context,
    _try_dev_login_cookie,
)
from orcheo_backend.app.authentication.settings import AuthSettings


def _base_settings(**overrides: object) -> AuthSettings:
    """Create a minimal AuthSettings for tests with reasonable defaults."""
    base = dict(
        mode="optional",
        jwt_secret=None,
        jwks_url=None,
        jwks_static=(),
        jwks_cache_ttl=300,
        jwks_timeout=5.0,
        allowed_algorithms=("HS256",),
        audiences=(),
        issuer=None,
        service_token_backend="sqlite",
        service_token_db_path=None,
        rate_limit_ip=0,
        rate_limit_identity=0,
        rate_limit_interval=60,
        dev_login_enabled=True,
        dev_login_cookie_name="orcheo_dev_session",
        dev_login_scopes=(),  # intentionally empty to trigger defaults
        dev_login_workspace_ids=(),
    )
    base.update(overrides)
    return AuthSettings(**base)  # type: ignore[arg-type]


def test_build_dev_context_uses_internal_default_scopes() -> None:
    """_build_dev_context falls back to built-in default scopes when empty."""

    settings = _base_settings(dev_login_scopes=())
    ctx = _build_dev_context("dev:alice", settings)

    # The internal default scopes include workflows and vault permissions
    assert "workflows:read" in ctx.scopes
    assert "workflows:execute" in ctx.scopes
    assert "vault:write" in ctx.scopes


def test_try_dev_login_cookie_returns_none_when_cookie_missing() -> None:
    """_try_dev_login_cookie returns None if the configured cookie is absent."""

    settings = _base_settings()

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],  # no Cookie header present
    }

    async def receive() -> dict[str, object]:
        return {"type": "http.request"}

    request = Request(scope, receive)  # type: ignore[arg-type]

    result = _try_dev_login_cookie(request, settings)
    assert result is None
