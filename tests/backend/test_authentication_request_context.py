"""RequestContext behaviour tests."""

from __future__ import annotations
from orcheo_backend.app.authentication import RequestContext


def test_request_context_anonymous() -> None:
    """RequestContext.anonymous() creates an anonymous context."""

    context = RequestContext.anonymous()

    assert context.subject == "anonymous"
    assert context.identity_type == "anonymous"
    assert not context.is_authenticated
    assert not context.has_scope("any-scope")


def test_request_context_is_authenticated() -> None:
    """is_authenticated returns True for non-anonymous contexts."""

    context = RequestContext(subject="user-123", identity_type="user")

    assert context.is_authenticated


def test_request_context_has_scope() -> None:
    """has_scope checks if a scope is present."""

    context = RequestContext(
        subject="svc",
        identity_type="service",
        scopes=frozenset({"workflows:read", "workflows:write"}),
    )

    assert context.has_scope("workflows:read")
    assert not context.has_scope("workflows:delete")
