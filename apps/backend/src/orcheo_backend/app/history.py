"""In-memory storage for workflow execution history and replay data."""

from __future__ import annotations
import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
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


class InMemoryRunHistoryStore:
    """Async-safe in-memory store for execution histories."""

    def __init__(self) -> None:
        """Initialize the in-memory store."""
        self._lock = asyncio.Lock()
        self._histories: dict[str, RunHistoryRecord] = {}

    async def start_run(
        self,
        *,
        workflow_id: str,
        execution_id: str,
        inputs: Mapping[str, Any] | None = None,
    ) -> RunHistoryRecord:
        """Initialise a history record for the provided execution."""
        async with self._lock:
            if execution_id in self._histories:
                msg = f"History already exists for execution_id={execution_id}"
                raise RunHistoryError(msg)

            record = RunHistoryRecord(
                workflow_id=workflow_id,
                execution_id=execution_id,
                inputs=dict(inputs or {}),
            )
            self._histories[execution_id] = record
            return record.model_copy(deep=True)

    async def append_step(
        self, execution_id: str, payload: Mapping[str, Any]
    ) -> RunHistoryStep:
        """Append a step for the execution."""
        async with self._lock:
            record = self._require_record(execution_id)
            return record.append_step(payload)

    async def mark_completed(self, execution_id: str) -> RunHistoryRecord:
        """Mark the execution as completed."""
        async with self._lock:
            record = self._require_record(execution_id)
            record.mark_completed()
            return record.model_copy(deep=True)

    async def mark_failed(self, execution_id: str, error: str) -> RunHistoryRecord:
        """Mark the execution as failed with the specified error message."""
        async with self._lock:
            record = self._require_record(execution_id)
            record.mark_failed(error)
            return record.model_copy(deep=True)

    async def mark_cancelled(
        self, execution_id: str, *, reason: str | None = None
    ) -> RunHistoryRecord:
        """Mark the execution as cancelled."""
        async with self._lock:
            record = self._require_record(execution_id)
            record.mark_cancelled(reason=reason)
            return record.model_copy(deep=True)

    async def get_history(self, execution_id: str) -> RunHistoryRecord:
        """Return a deep copy of the execution history."""
        async with self._lock:
            record = self._require_record(execution_id)
            return record.model_copy(deep=True)

    async def clear(self) -> None:
        """Clear all stored histories. Intended for testing only."""
        async with self._lock:
            self._histories.clear()

    def _require_record(self, execution_id: str) -> RunHistoryRecord:
        """Return the record or raise an error if missing."""
        record = self._histories.get(execution_id)
        if record is None:
            msg = f"History not found for execution_id={execution_id}"
            raise RunHistoryNotFoundError(msg)
        return record


__all__ = [
    "InMemoryRunHistoryStore",
    "RunHistoryError",
    "RunHistoryNotFoundError",
    "RunHistoryRecord",
    "RunHistoryStep",
]
