"""Context manager utilities for binding credential resolvers."""

from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:  # pragma: no cover - typing only
    from .resolver import CredentialResolver


_ACTIVE_RESOLVER: ContextVar[CredentialResolver | None] = ContextVar(
    "orcheo_active_credential_resolver", default=None
)


@contextmanager
def credential_resolution(
    resolver: CredentialResolver | None,
) -> Any:
    """Install ``resolver`` for the duration of the context manager."""
    if resolver is None:
        yield None
        return
    token = _ACTIVE_RESOLVER.set(resolver)
    try:
        yield resolver
    finally:
        _ACTIVE_RESOLVER.reset(token)


def get_active_credential_resolver() -> CredentialResolver | None:
    """Return the credential resolver currently bound to the execution context."""
    return _ACTIVE_RESOLVER.get()


__all__ = ["credential_resolution", "get_active_credential_resolver"]
