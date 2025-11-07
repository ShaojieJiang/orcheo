"""Shared typing utilities for the SQLite ChatKit store."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:  # pragma: no cover - typing helper only
    from orcheo_backend.app.chatkit_service import ChatKitRequestContext as _Context
else:  # pragma: no cover - runtime fallback
    _Context = dict[str, Any]

ChatKitRequestContext = _Context

__all__ = ["ChatKitRequestContext"]
