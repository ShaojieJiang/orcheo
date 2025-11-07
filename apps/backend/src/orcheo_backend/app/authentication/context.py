from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RequestContext:
    """Authenticated identity attached to a request or WebSocket."""

    subject: str
    identity_type: str
    scopes: frozenset[str] = field(default_factory=frozenset)
    workspace_ids: frozenset[str] = field(default_factory=frozenset)
    token_id: str | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    claims: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        """Return True when the context represents an authenticated identity."""
        return self.identity_type != "anonymous"

    def has_scope(self, scope: str) -> bool:
        """Return True when the identity possesses the given scope."""
        return scope in self.scopes

    @classmethod
    def anonymous(cls) -> RequestContext:
        """Return a sentinel context representing unauthenticated access."""
        return cls(subject="anonymous", identity_type="anonymous")
