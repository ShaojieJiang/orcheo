"""Caching utilities for the Orcheo CLI."""

from __future__ import annotations
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from orcheo_sdk.cli.errors import CLIError


_CACHE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9_.-]")


@dataclass(slots=True)
class CacheEntry:
    """Payload saved in the CLI cache."""

    payload: Any
    timestamp: datetime
    ttl: timedelta

    @property
    def is_stale(self) -> bool:
        """Return whether the entry has expired."""
        expiry = self.timestamp + self.ttl
        now = datetime.now(tz=UTC)
        return now > expiry


@dataclass(slots=True)
class CacheManager:
    """Simple JSON-based cache with time-based expiration."""

    directory: Path
    ttl: timedelta

    def __post_init__(self) -> None:
        """Create the cache directory if it does not already exist."""
        self.directory.mkdir(parents=True, exist_ok=True)

    def load(self, key: str) -> CacheEntry | None:
        """Return the cached entry for ``key`` if present."""
        path = self._path_for_key(key)
        if not path.exists():
            return None

        data = json.loads(path.read_text(encoding="utf-8"))
        timestamp = datetime.fromisoformat(data["timestamp"])
        payload = data["payload"]
        entry = CacheEntry(payload=payload, timestamp=timestamp, ttl=self.ttl)
        return entry

    def store(self, key: str, payload: Any) -> None:
        """Persist ``payload`` for ``key``."""
        path = self._path_for_key(key)
        document = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "payload": payload,
        }
        serialized = json.dumps(document, indent=2, sort_keys=True)
        path.write_text(serialized, encoding="utf-8")

    def invalidate(self, key: str) -> None:
        """Remove cached payload for ``key`` when present."""
        path = self._path_for_key(key)
        if path.exists():
            path.unlink()

    def fetch(self, key: str, loader: Callable[[], Any]) -> tuple[Any, bool, bool]:
        """Return cached or freshly loaded payload for ``key``.

        Returns a tuple of ``(payload, from_cache, is_stale)`` where ``from_cache``
        indicates whether cached data was used and ``is_stale`` captures whether
        the cached entry has exceeded the configured TTL.
        """
        try:
            payload = loader()
        except CLIError as error:
            entry = self.load(key)
            if entry is None:
                raise error
            return entry.payload, True, entry.is_stale
        except Exception as exc:  # pragma: no cover - defensive fallback
            raise CLIError(str(exc)) from exc
        self.store(key, payload)
        return payload, False, False

    def load_or_raise(self, key: str) -> Any:
        """Return cached payload or raise if missing."""
        entry = self.load(key)
        if entry is None:
            msg = f"Cached payload for {key!r} not found."
            raise CLIError(msg)
        return entry.payload

    def _path_for_key(self, key: str) -> Path:
        safe_key = _CACHE_FILENAME_PATTERN.sub("_", key)
        return self.directory / f"{safe_key}.json"
