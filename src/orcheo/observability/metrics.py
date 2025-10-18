"""Observability metrics helpers for product success tracking."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class SuccessMetricsSnapshot:
    """Immutable snapshot of aggregated success metrics."""

    recorded_at: datetime
    uv_installs: int
    github_stars: int
    quickstart_completions: int
    failure_backlog: int


@dataclass
class SuccessMetricsTracker:
    """Track product success metrics over time."""

    uv_installs: int = 0
    github_stars: int = 0
    quickstart_completions: int = 0
    failure_backlog: int = 0
    _history: list[SuccessMetricsSnapshot] = field(default_factory=list)

    def record_uv_install(self, count: int = 1) -> None:
        """Increment the uv install counter."""
        self.uv_installs += count
        self._checkpoint()

    def record_github_star(self, count: int = 1) -> None:
        """Increment the GitHub star counter."""
        self.github_stars += count
        self._checkpoint()

    def record_quickstart_completion(self, count: int = 1) -> None:
        """Increment the quickstart completion counter."""
        self.quickstart_completions += count
        self._checkpoint()

    def record_failure(self, count: int = 1) -> None:
        """Increase the failure backlog."""
        self.failure_backlog += count
        self._checkpoint()

    def resolve_failure(self, count: int = 1) -> None:
        """Decrease the failure backlog while avoiding negative totals."""
        self.failure_backlog = max(0, self.failure_backlog - count)
        self._checkpoint()

    def summary(self) -> dict[str, int]:
        """Return the latest totals for the metrics."""
        return {
            "uv_installs": self.uv_installs,
            "github_stars": self.github_stars,
            "quickstart_completions": self.quickstart_completions,
            "failure_backlog": self.failure_backlog,
        }

    def history(self) -> list[SuccessMetricsSnapshot]:
        """Return historical snapshots captured after each update."""
        return list(self._history)

    def _checkpoint(self) -> None:
        """Persist a snapshot of the current metrics."""
        self._history.append(
            SuccessMetricsSnapshot(
                recorded_at=datetime.now(tz=UTC),
                uv_installs=self.uv_installs,
                github_stars=self.github_stars,
                quickstart_completions=self.quickstart_completions,
                failure_backlog=self.failure_backlog,
            )
        )


__all__ = ["SuccessMetricsSnapshot", "SuccessMetricsTracker"]
