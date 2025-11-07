"""Async-safe in-memory history store implementation."""

from __future__ import annotations
import asyncio
from collections.abc import Mapping
from typing import Any
from orcheo_backend.app.history.models import (
    RunHistoryError,
    RunHistoryNotFoundError,
    RunHistoryRecord,
    RunHistoryStep,
)


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
        self,
        execution_id: str,
        payload: Mapping[str, Any],
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
        self,
        execution_id: str,
        *,
        reason: str | None = None,
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

    async def list_histories(
        self,
        workflow_id: str,
        *,
        limit: int | None = None,
    ) -> list[RunHistoryRecord]:
        """Return histories associated with the provided workflow."""
        async with self._lock:
            records = [
                record.model_copy(deep=True)
                for record in self._histories.values()
                if record.workflow_id == workflow_id
            ]

        records.sort(key=lambda record: record.started_at, reverse=True)
        if limit is not None:
            return records[:limit]
        return records

    def _require_record(self, execution_id: str) -> RunHistoryRecord:
        """Return the record or raise an error if missing."""
        record = self._histories.get(execution_id)
        if record is None:
            msg = f"History not found for execution_id={execution_id}"
            raise RunHistoryNotFoundError(msg)
        return record


__all__ = ["InMemoryRunHistoryStore"]
