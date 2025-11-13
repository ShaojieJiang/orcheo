"""Shared models and protocol for workflow execution history."""

from __future__ import annotations
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(tz=UTC)


class RunHistoryError(RuntimeError):
    """Base error raised for run history store issues."""


class RunHistoryNotFoundError(RunHistoryError):
    """Raised when requesting history for an unknown execution."""


class RunHistoryStep(BaseModel):
    """Single step captured during workflow execution."""

    model_config = ConfigDict(extra="forbid")

    index: int
    at: datetime = Field(default_factory=_utcnow)
    payload: dict[str, Any]


class RunHistoryRecord(BaseModel):
    """Complete history for a workflow execution."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    workflow_id: str
    execution_id: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    status: str = "running"
    started_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None
    error: str | None = None
    steps: list[RunHistoryStep] = Field(default_factory=list)
    trace_id: str | None = None
    trace_started_at: datetime | None = None
    trace_updated_at: datetime | None = None

    def append_step(self, payload: Mapping[str, Any]) -> RunHistoryStep:
        """Append a step to the history with an auto-incremented index."""
        step = RunHistoryStep(index=len(self.steps), payload=dict(payload))
        self.steps.append(step)
        return step

    def mark_completed(self) -> None:
        """Mark the execution as successfully completed."""
        self.status = "completed"
        self.completed_at = _utcnow()
        self.error = None

    def mark_failed(self, error: str) -> None:
        """Mark the execution as failed with the provided error."""
        self.status = "error"
        self.completed_at = _utcnow()
        self.error = error

    def mark_cancelled(self, *, reason: str | None = None) -> None:
        """Mark the execution as cancelled with an optional reason."""
        self.status = "cancelled"
        self.completed_at = _utcnow()
        self.error = reason

    def update_trace_metadata(
        self,
        *,
        trace_id: str | None = None,
        started_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """Update the stored trace metadata for the execution."""
        if trace_id is not None:
            self.trace_id = trace_id
        if started_at is not None:
            self.trace_started_at = started_at
        if updated_at is not None:
            self.trace_updated_at = updated_at


class RunHistoryStore(Protocol):
    """Protocol describing history store behaviours."""

    async def start_run(
        self,
        *,
        workflow_id: str,
        execution_id: str,
        inputs: Mapping[str, Any] | None = None,
    ) -> RunHistoryRecord:
        """Initialise a history record for the provided execution."""

    async def append_step(
        self,
        execution_id: str,
        payload: Mapping[str, Any],
    ) -> RunHistoryStep:
        """Append a step for the execution."""

    async def mark_completed(self, execution_id: str) -> RunHistoryRecord:
        """Mark the execution as completed."""

    async def mark_failed(
        self,
        execution_id: str,
        error: str,
    ) -> RunHistoryRecord:
        """Mark the execution as failed with the specified error."""

    async def mark_cancelled(
        self,
        execution_id: str,
        *,
        reason: str | None = None,
    ) -> RunHistoryRecord:
        """Mark the execution as cancelled."""

    async def get_history(self, execution_id: str) -> RunHistoryRecord:
        """Return a deep copy of the execution history."""

    async def clear(self) -> None:
        """Clear all stored histories. Intended for testing only."""

    async def list_histories(
        self,
        workflow_id: str,
        *,
        limit: int | None = None,
    ) -> list[RunHistoryRecord]:
        """Return histories associated with the provided workflow."""

    async def update_trace_metadata(
        self,
        execution_id: str,
        *,
        trace_id: str | None = None,
        started_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> RunHistoryRecord:
        """Persist trace identifiers and timestamps for the execution."""


__all__ = [
    "RunHistoryError",
    "RunHistoryNotFoundError",
    "RunHistoryRecord",
    "RunHistoryStep",
    "RunHistoryStore",
]
