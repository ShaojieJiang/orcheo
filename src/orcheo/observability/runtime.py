"""Runtime observability helpers for execution metrics."""

from __future__ import annotations
import statistics
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class MetricSample:
    """Represents a single recorded metric sample."""

    workflow_id: str
    name: str
    value: float
    recorded_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


class MetricsRecorder:
    """In-memory metrics recorder used for observability dashboards."""

    def __init__(self) -> None:
        """Initialize an empty metrics recorder."""
        self._samples: list[MetricSample] = []

    def record(self, workflow_id: str, name: str, value: float) -> None:
        """Record a metric sample for the workflow."""
        sample = MetricSample(workflow_id=workflow_id, name=name, value=value)
        self._samples.append(sample)

    def reset(self) -> None:
        """Clear all recorded samples."""
        self._samples.clear()

    def samples(self) -> Iterable[MetricSample]:
        """Return all recorded samples."""
        return list(self._samples)

    def summarize(self, workflow_id: str, name: str) -> dict[str, float] | None:
        """Return summary statistics for a metric or ``None`` if no samples exist."""
        values = [
            sample.value
            for sample in self._samples
            if sample.workflow_id == workflow_id and sample.name == name
        ]
        if not values:
            return None
        return {
            "count": len(values),
            "avg": statistics.fmean(values),
            "max": max(values),
            "min": min(values),
        }

    def group_by_metric(self) -> dict[str, list[MetricSample]]:
        """Return samples grouped by metric name."""
        grouped: dict[str, list[MetricSample]] = defaultdict(list)
        for sample in self._samples:
            grouped[sample.name].append(sample)
        return grouped


_metrics_recorder = MetricsRecorder()


def get_metrics_recorder() -> MetricsRecorder:
    """Return the global metrics recorder instance."""
    return _metrics_recorder


__all__ = ["MetricSample", "MetricsRecorder", "get_metrics_recorder"]
