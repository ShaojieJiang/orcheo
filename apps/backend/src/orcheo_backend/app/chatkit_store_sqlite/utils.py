"""Utility helpers shared by the SQLite ChatKit store modules."""

from __future__ import annotations
import json
from datetime import UTC, datetime
from typing import Any


def now_utc() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(tz=UTC)


def to_isoformat(value: datetime) -> str:
    """Return an ISO-8601 string, ensuring the value is timezone-aware."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def compact_json(payload: Any) -> str:
    """Serialize ``payload`` with deterministic separators."""
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


__all__ = ["now_utc", "to_isoformat", "compact_json"]
