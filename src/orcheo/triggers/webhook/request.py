"""Request data structures used during webhook validation."""

from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class WebhookRequest:
    """Normalized representation of an inbound webhook request."""

    method: str
    headers: Mapping[str, str]
    query_params: Mapping[str, str]
    payload: Any
    source_ip: str | None = None

    def normalized_method(self) -> str:
        """Return the uppercase HTTP method."""
        return self.method.upper()

    def normalized_headers(self) -> dict[str, str]:
        """Return headers normalized to lowercase keys."""
        return {key.lower(): value for key, value in self.headers.items()}

    def normalized_query(self) -> dict[str, str]:
        """Return a shallow copy of the query parameters."""
        return dict(self.query_params)


__all__ = ["WebhookRequest"]
