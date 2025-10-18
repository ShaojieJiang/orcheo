"""Success metrics tracking utilities."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal


MetricKind = Literal[
    "uv_install",
    "github_star",
    "quickstart_completion",
    "workflow_failure",
]


@dataclass(slots=True)
class MetricsEvent:
    """Represents a single metrics event that should be counted."""

    kind: MetricKind
    at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SuccessMetricsTracker:
    """Aggregate metrics across different success indicators."""

    uv_installs: int = 0
    github_stars: int = 0
    quickstart_completions: int = 0
    workflow_failures: int = 0
    events: list[MetricsEvent] = field(default_factory=list)

    def ingest(self, event: MetricsEvent) -> None:
        """Update counters based on the provided event."""
        self.events.append(event)
        match event.kind:
            case "uv_install":
                self.uv_installs += 1
            case "github_star":
                self.github_stars += 1
            case "quickstart_completion":
                self.quickstart_completions += 1
            case "workflow_failure":
                self.workflow_failures += 1

    def to_dashboard(self) -> dict[str, Any]:
        """Return a serialisable representation of tracked metrics."""
        events = []
        for event in self.events:
            metadata: dict[str, Any] = {"region": None}
            metadata.update(event.metadata)
            record = {"kind": event.kind, "at": event.at.isoformat(), **metadata}
            events.append(record)
        return {
            "uv_installs": self.uv_installs,
            "github_stars": self.github_stars,
            "quickstart_completions": self.quickstart_completions,
            "workflow_failures": self.workflow_failures,
            "events": events,
        }
