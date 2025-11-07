"""Authorization policy and dependency helper tests."""

from __future__ import annotations
import pytest
from orcheo_backend.app.authentication import (
    AuthorizationError,
    AuthorizationPolicy,
    RequestContext,
    ensure_scopes,
    ensure_workspace_access,
    require_scopes,
    require_workspace_access,
)


def test_ensure_scopes_allows_present_scopes() -> None:
    """ensure_scopes succeeds when all required scopes are present."""

    context = RequestContext(
        subject="svc",
        identity_type="service",
        scopes=frozenset({"workflows:read", "workflows:write"}),
    )

    ensure_scopes(context, ["workflows:read"])


def test_ensure_scopes_raises_on_missing_scope() -> None:
    """ensure_scopes raises AuthorizationError when scopes are missing."""

    context = RequestContext(
        subject="svc",
        identity_type="service",
        scopes=frozenset({"workflows:read"}),
    )

    with pytest.raises(AuthorizationError) as exc:
        ensure_scopes(context, ["workflows:write"])

    assert "Missing required scopes" in str(exc.value)


def test_ensure_workspace_access_allows_subset() -> None:
    """Callers with matching workspace IDs pass the authorization check."""

    context = RequestContext(
        subject="svc",
        identity_type="service",
        workspace_ids=frozenset({"ws-1", "ws-2"}),
    )

    ensure_workspace_access(context, ["ws-2"])


def test_ensure_workspace_access_raises_for_missing_workspace() -> None:
    """Missing workspace authorization raises AuthorizationError."""

    context = RequestContext(
        subject="svc",
        identity_type="service",
        workspace_ids=frozenset({"ws-1"}),
    )

    with pytest.raises(AuthorizationError):
        ensure_workspace_access(context, ["ws-2"])


def test_authorization_policy_enforces_scopes_and_workspaces() -> None:
    """AuthorizationPolicy should gate scopes and workspace access."""

    context = RequestContext(
        subject="user-1",
        identity_type="user",
        scopes=frozenset({"chatkit:session"}),
        workspace_ids=frozenset({"ws-1"}),
    )
    policy = AuthorizationPolicy(context)

    assert policy.require_authenticated() is context
    assert policy.require_scopes("chatkit:session") is context
    assert policy.require_workspace("ws-1") is context

    with pytest.raises(AuthorizationError):
        policy.require_workspace("ws-2")


@pytest.mark.asyncio
async def test_require_scopes_dependency_enforces_missing_scope() -> None:
    """require_scopes integrates with authenticate_request for FastAPI routes."""

    dependency = require_scopes("workflows:write")
    context = RequestContext(
        subject="svc",
        identity_type="service",
        scopes=frozenset({"workflows:read"}),
    )

    with pytest.raises(AuthorizationError):
        await dependency(context)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_require_workspace_access_dependency_allows_valid_context() -> None:
    """require_workspace_access allows contexts authorized for the workspace."""

    dependency = require_workspace_access("ws-1")
    context = RequestContext(
        subject="svc",
        identity_type="service",
        workspace_ids=frozenset({"ws-1", "ws-2"}),
    )

    result = await dependency(context)  # type: ignore[arg-type]

    assert result is context
