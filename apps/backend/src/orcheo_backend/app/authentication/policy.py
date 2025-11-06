from __future__ import annotations
from collections.abc import Awaitable, Callable, Iterable
from fastapi import Depends, status
from .context import RequestContext
from .dependencies import get_request_context
from .errors import AuthenticationError, AuthorizationError


class AuthorizationPolicy:
    """Evaluate authorization decisions based on a request context."""

    def __init__(self, context: RequestContext) -> None:
        """Bind the policy to the authenticated request context."""
        self._context = context

    @property
    def context(self) -> RequestContext:
        """Return the underlying request context."""
        return self._context

    def require_authenticated(self) -> RequestContext:
        """Ensure the request is associated with an authenticated identity."""
        if not self._context.is_authenticated:
            raise AuthenticationError(
                "Authentication required",
                code="auth.authentication_required",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return self._context

    def require_scopes(self, *scopes: str) -> RequestContext:
        """Ensure the identity possesses the provided scopes."""
        ensure_scopes(self._context, scopes)
        return self._context

    def require_workspace(self, workspace_id: str) -> RequestContext:
        """Ensure the identity is authorised for the workspace."""
        ensure_workspace_access(self._context, [workspace_id])
        return self._context

    def require_workspaces(self, workspace_ids: Iterable[str]) -> RequestContext:
        """Ensure the identity can access all provided workspaces."""
        ensure_workspace_access(self._context, workspace_ids)
        return self._context


def ensure_scopes(context: RequestContext, scopes: Iterable[str]) -> None:
    """Ensure the request context possesses all required scopes."""
    missing = [scope for scope in scopes if scope and scope not in context.scopes]
    if missing:
        raise AuthorizationError(
            "Missing required scopes: " + ", ".join(sorted(missing)),
            code="auth.missing_scope",
        )


def ensure_workspace_access(
    context: RequestContext, workspace_ids: Iterable[str]
) -> None:
    """Ensure the context is authorized for the requested workspace identifiers."""
    required = {workspace_id for workspace_id in workspace_ids if workspace_id}
    if not required:
        return
    if not context.workspace_ids:
        raise AuthorizationError(
            "Workspace access denied", code="auth.workspace_forbidden"
        )
    if not required.issubset(context.workspace_ids):
        missing = sorted(required.difference(context.workspace_ids))
        raise AuthorizationError(
            "Workspace access denied for: " + ", ".join(missing),
            code="auth.workspace_forbidden",
        )


def require_scopes(*scopes: str) -> Callable[..., Awaitable[RequestContext]]:
    """Return a FastAPI dependency that enforces required scopes."""

    async def dependency(
        context: RequestContext = Depends(get_request_context),  # noqa: B008
    ) -> RequestContext:
        ensure_scopes(context, scopes)
        return context

    return dependency


def require_workspace_access(
    *workspace_ids: str,
) -> Callable[..., Awaitable[RequestContext]]:
    """Return a dependency that ensures the caller may access the workspace."""

    async def dependency(
        context: RequestContext = Depends(get_request_context),  # noqa: B008
    ) -> RequestContext:
        ensure_workspace_access(context, workspace_ids)
        return context

    return dependency


def get_authorization_policy(
    context: RequestContext = Depends(get_request_context),  # noqa: B008
) -> AuthorizationPolicy:
    """Return an AuthorizationPolicy bound to the active request context."""
    return AuthorizationPolicy(context)


__all__ = [
    "AuthorizationPolicy",
    "ensure_scopes",
    "ensure_workspace_access",
    "require_scopes",
    "require_workspace_access",
    "get_authorization_policy",
]
