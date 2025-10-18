"""Lightweight metrics recorder used for observability dashboards."""

from __future__ import annotations
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class MetricEvent:
    """Represents a single metric datapoint."""

    name: str
    value: float
    tags: dict[str, str] = field(default_factory=dict)
    recorded_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


class MetricRecorder:
    """In-memory recorder for aggregating metric events."""

    def __init__(self) -> None:
        """Initialise an empty recorder."""
        self._events: list[MetricEvent] = []

    def record(self, event: MetricEvent) -> None:
        """Record a metric event."""
        self._events.append(event)

    def extend(self, events: Iterable[MetricEvent]) -> None:
        """Record multiple metric events at once."""
        for event in events:
            self.record(event)

    def summary(self) -> dict[str, dict[str, float]]:
        """Return aggregated metrics grouped by metric name and tag."""
        aggregates: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        for event in self._events:
            tag_pairs = (f"{key}={value}" for key, value in sorted(event.tags.items()))
            tags_key = ",".join(tag_pairs)
            aggregates[event.name][tags_key] += event.value
        return {name: dict(values) for name, values in aggregates.items()}

    def clear(self) -> None:
        """Clear recorded metrics (useful in tests)."""
        self._events.clear()


metrics = MetricRecorder()


__all__ = ["MetricEvent", "MetricRecorder", "metrics"]
