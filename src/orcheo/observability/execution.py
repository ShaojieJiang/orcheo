"""Execution viewer instrumentation primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Iterable, Mapping


@dataclass(slots=True)
class ExecutionArtifact:
    """Represents a downloadable artifact emitted by a step."""

    name: str
    url: str
    content_type: str | None = None


@dataclass(slots=True)
class ExecutionStep:
    """Single workflow execution step with prompt/response metadata."""

    id: str
    name: str
    started_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    completed_at: datetime | None = None
    prompt: str | None = None
    response: str | None = None
    tokens_consumed: int = 0
    metrics: Mapping[str, float] = field(default_factory=dict)
    artifacts: list[ExecutionArtifact] = field(default_factory=list)

    def mark_completed(
        self,
        *,
        response: str | None = None,
        tokens: int | None = None,
        metrics: Mapping[str, float] | None = None,
        artifacts: Iterable[ExecutionArtifact] | None = None,
    ) -> None:
        """Mark the step as completed and update runtime metadata."""

        self.completed_at = datetime.now(tz=UTC)
        if response is not None:
            self.response = response
        if tokens is not None:
            self.tokens_consumed = tokens
        if metrics is not None:
            self.metrics = dict(metrics)
        if artifacts is not None:
            self.artifacts = list(artifacts)

    @property
    def duration_seconds(self) -> float | None:
        """Return the runtime duration for the step in seconds."""

        if self.completed_at is None:
            return None
        delta = self.completed_at - self.started_at
        return delta.total_seconds()


@dataclass(slots=True)
class ExecutionTrace:
    """Aggregates execution steps for observability dashboards."""

    workflow_id: str
    run_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    steps: list[ExecutionStep] = field(default_factory=list)

    def add_step(self, step: ExecutionStep) -> None:
        """Append a new execution step to the trace."""

        self.steps.append(step)

    def record_step(
        self,
        *,
        step_id: str,
        name: str,
        prompt: str | None = None,
    ) -> ExecutionStep:
        """Create, append, and return a new step instance."""

        step = ExecutionStep(id=step_id, name=name, prompt=prompt)
        self.add_step(step)
        return step

    def total_tokens(self) -> int:
        """Return the total number of tokens consumed by the trace."""

        return sum(step.tokens_consumed for step in self.steps)

    def prompts(self) -> list[str]:
        """Return a list of prompts emitted by the trace."""

        return [step.prompt for step in self.steps if step.prompt]

    def responses(self) -> list[str]:
        """Return a list of responses captured by the trace."""

        return [step.response for step in self.steps if step.response]

    def to_dashboard(self) -> dict[str, object]:
        """Serialize the trace for the execution viewer dashboard."""

        return {
            "workflow_id": self.workflow_id,
            "run_id": self.run_id,
            "created_at": self.created_at.isoformat(),
            "total_tokens": self.total_tokens(),
            "steps": [
                {
                    "id": step.id,
                    "name": step.name,
                    "prompt": step.prompt,
                    "response": step.response,
                    "tokens": step.tokens_consumed,
                    "duration_seconds": step.duration_seconds,
                    "metrics": dict(step.metrics),
                    "artifacts": [asdict(artifact) for artifact in step.artifacts],
                }
                for step in self.steps
            ],
        }


__all__ = ["ExecutionArtifact", "ExecutionStep", "ExecutionTrace"]
