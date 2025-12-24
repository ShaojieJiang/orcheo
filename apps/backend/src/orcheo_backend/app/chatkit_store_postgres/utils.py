"""Utility helpers shared by the PostgreSQL ChatKit store."""

from __future__ import annotations
import json
from datetime import UTC, datetime
from typing import Any


def now_utc() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(tz=UTC)


def ensure_datetime(value: datetime) -> datetime:
    """Return a timezone-aware datetime."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def compact_json(payload: Any) -> str:
    """Serialize ``payload`` with deterministic separators."""
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


__all__ = ["compact_json", "ensure_datetime", "now_utc"]
