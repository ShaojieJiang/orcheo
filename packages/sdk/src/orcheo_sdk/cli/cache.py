"""Response caching utilities for the Orcheo CLI."""

from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class CacheEntry:
    """Cached response payload stored on disk."""

    data: Any
    timestamp: datetime


class CacheStore:
    """Store JSON responses for offline reuse."""

    def __init__(self, root: Path) -> None:
        """Create a cache store rooted at the provided directory."""
        self.root = root
        self._responses_dir = self.root / "responses"

    def ensure(self) -> None:
        """Ensure the cache directory exists."""
        self._responses_dir.mkdir(parents=True, exist_ok=True)

    def build_key(
        self, method: str, path: str, params: dict[str, Any] | None = None
    ) -> str:
        """Return a deterministic key for the given HTTP request."""
        method = method.upper()
        base = f"{method} {path}"
        if params:
            serialized = json.dumps(params, sort_keys=True, separators=(",", ":"))
            base = f"{base}?{serialized}"
        digest = hashlib.sha256(base.encode("utf-8")).hexdigest()
        return digest

    def _entry_path(self, key: str) -> Path:
        return self._responses_dir / f"{key}.json"

    def write(self, key: str, data: Any) -> None:
        """Persist a payload to the cache."""
        path = self._entry_path(key)
        payload = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "data": data,
        }
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def read(self, key: str) -> CacheEntry | None:
        """Return a cached payload if present."""
        path = self._entry_path(key)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        timestamp_raw = payload.get("timestamp")
        timestamp: datetime | None = None
        if isinstance(timestamp_raw, str):
            timestamp = datetime.fromisoformat(timestamp_raw)
        if timestamp is None:
            timestamp = datetime.now(tz=UTC)
        return CacheEntry(data=payload.get("data"), timestamp=timestamp)


__all__ = ["CacheEntry", "CacheStore"]
