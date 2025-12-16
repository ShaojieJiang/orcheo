"""Lightweight counters for ChatKit server events."""

from __future__ import annotations
from collections import Counter


class ChatKitTelemetry:
    """In-memory telemetry aggregator for ChatKit server events."""

    def __init__(self) -> None:
        """Initialise the counter store."""
        self._counters: Counter[str] = Counter()

    def increment(self, key: str, *, amount: int = 1) -> None:
        """Increase a named counter by ``amount``."""
        if amount <= 0:  # pragma: no cover - defensive
            return
        self._counters[key] += amount

    def metrics(self) -> dict[str, int]:
        """Return a snapshot of current counters."""
        return dict(self._counters)

    def reset(self) -> None:
        """Clear all counters (used in tests)."""
        self._counters.clear()


chatkit_telemetry = ChatKitTelemetry()

__all__ = ["ChatKitTelemetry", "chatkit_telemetry"]
