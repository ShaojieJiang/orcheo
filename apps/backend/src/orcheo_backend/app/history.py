"""Storage abstractions for workflow execution history and replay data."""

from __future__ import annotations
import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
import aiosqlite
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


class SqliteRunHistoryStore:
    """SQLite-backed store for execution histories shared across processes."""

    def __init__(self, database_path: str | Path) -> None:
        """Initialise the persistent history store."""
        self._database_path = Path(database_path).expanduser()
        self._lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def start_run(
        self,
        *,
        workflow_id: str,
        execution_id: str,
        inputs: Mapping[str, Any] | None = None,
    ) -> RunHistoryRecord:
        """Initialise a history record for the provided execution."""
        await self._ensure_initialized()
        async with self._lock:
            started_at = _utcnow()
            payload = json.dumps(dict(inputs or {}))
            async with self._connection() as conn:
                try:
                    await conn.execute(
                        """
                        INSERT INTO execution_history (
                            execution_id,
                            workflow_id,
                            inputs,
                            status,
                            started_at,
                            completed_at,
                            error
                        )
                        VALUES (?, ?, ?, ?, ?, NULL, NULL)
                        """,
                        (
                            execution_id,
                            workflow_id,
                            payload,
                            "running",
                            started_at.isoformat(),
                        ),
                    )
                    await conn.commit()
                except aiosqlite.IntegrityError as exc:  # pragma: no cover - defensive
                    msg = f"History already exists for execution_id={execution_id}"
                    raise RunHistoryError(msg) from exc
            return RunHistoryRecord(
                workflow_id=workflow_id,
                execution_id=execution_id,
                inputs=json.loads(payload),
                status="running",
                started_at=started_at,
                steps=[],
            )

    async def append_step(
        self,
        execution_id: str,
        payload: Mapping[str, Any],
    ) -> RunHistoryStep:
        """Append a step for the execution."""
        await self._ensure_initialized()
        async with self._lock:
            at = _utcnow()
            async with self._connection() as conn:
                record_row = await self._get_record_row(conn, execution_id)
                if record_row is None:
                    msg = f"History not found for execution_id={execution_id}"
                    raise RunHistoryNotFoundError(msg)

                cursor = await conn.execute(
                    """
                    SELECT COALESCE(MAX(step_index), -1) AS current_index
                      FROM execution_history_steps
                     WHERE execution_id = ?
                    """,
                    (execution_id,),
                )
                row = await cursor.fetchone()
                next_index = (row["current_index"] if row else -1) + 1

                await conn.execute(
                    """
                    INSERT INTO execution_history_steps (
                        execution_id,
                        step_index,
                        at,
                        payload
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        execution_id,
                        next_index,
                        at.isoformat(),
                        json.dumps(dict(payload)),
                    ),
                )
                await conn.commit()
            return RunHistoryStep(
                index=next_index,
                at=at,
                payload=dict(payload),
            )

    async def mark_completed(self, execution_id: str) -> RunHistoryRecord:
        """Mark the execution as completed."""
        return await self._update_status(
            execution_id,
            status="completed",
            error=None,
        )

    async def mark_failed(
        self,
        execution_id: str,
        error: str,
    ) -> RunHistoryRecord:
        """Mark the execution as failed with the specified error message."""
        return await self._update_status(
            execution_id,
            status="error",
            error=error,
        )

    async def mark_cancelled(
        self,
        execution_id: str,
        *,
        reason: str | None = None,
    ) -> RunHistoryRecord:
        """Mark the execution as cancelled."""
        return await self._update_status(
            execution_id,
            status="cancelled",
            error=reason,
        )

    async def get_history(self, execution_id: str) -> RunHistoryRecord:
        """Return a deep copy of the execution history."""
        await self._ensure_initialized()
        async with self._connection() as conn:
            record_row = await self._get_record_row(conn, execution_id)
            if record_row is None:
                msg = f"History not found for execution_id={execution_id}"
                raise RunHistoryNotFoundError(msg)
            steps = await self._load_steps(conn, execution_id)
            return self._row_to_record(record_row, steps)

    async def clear(self) -> None:
        """Clear all stored histories. Intended for testing only."""
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                await conn.execute("DELETE FROM execution_history_steps")
                await conn.execute("DELETE FROM execution_history")
                await conn.commit()

    async def _update_status(
        self,
        execution_id: str,
        *,
        status: str,
        error: str | None,
    ) -> RunHistoryRecord:
        """Persist the execution status mutation and return the updated record."""
        await self._ensure_initialized()
        async with self._lock:
            completed_at = _utcnow()
            async with self._connection() as conn:
                cursor = await conn.execute(
                    """
                    UPDATE execution_history
                       SET status = ?,
                           completed_at = ?,
                           error = ?
                     WHERE execution_id = ?
                    """,
                    (
                        status,
                        completed_at.isoformat(),
                        error,
                        execution_id,
                    ),
                )
                if cursor.rowcount == 0:
                    msg = f"History not found for execution_id={execution_id}"
                    raise RunHistoryNotFoundError(msg)
                await conn.commit()
                record_row = await self._get_record_row(conn, execution_id)
                if record_row is None:  # pragma: no cover - defensive
                    msg = f"History not found for execution_id={execution_id}"
                    raise RunHistoryNotFoundError(msg)
                steps = await self._load_steps(conn, execution_id)
            record = self._row_to_record(record_row, steps)
            record.completed_at = completed_at
            record.status = status
            record.error = error
            return record

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """Return a configured SQLite connection."""
        conn = await aiosqlite.connect(self._database_path)
        try:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON;")
            yield conn
        finally:
            await conn.close()

    async def _ensure_initialized(self) -> None:
        """Create the required tables if they are missing."""
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return
            self._database_path.parent.mkdir(parents=True, exist_ok=True)
            async with self._connection() as conn:
                await conn.executescript(
                    """
                    PRAGMA journal_mode = WAL;
                    CREATE TABLE IF NOT EXISTS execution_history (
                        execution_id TEXT PRIMARY KEY,
                        workflow_id TEXT NOT NULL,
                        inputs TEXT NOT NULL,
                        status TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        completed_at TEXT,
                        error TEXT
                    );
                    CREATE TABLE IF NOT EXISTS execution_history_steps (
                        execution_id TEXT NOT NULL,
                        step_index INTEGER NOT NULL,
                        at TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        PRIMARY KEY (execution_id, step_index),
                        FOREIGN KEY (execution_id)
                            REFERENCES execution_history(execution_id)
                            ON DELETE CASCADE
                    );
                    CREATE INDEX IF NOT EXISTS idx_history_steps_execution
                        ON execution_history_steps(execution_id, step_index);
                    """
                )
                await conn.commit()
            self._initialized = True

    async def _get_record_row(
        self,
        conn: aiosqlite.Connection,
        execution_id: str,
    ) -> aiosqlite.Row | None:
        """Return the raw row for an execution if it exists."""
        cursor = await conn.execute(
            """
            SELECT
                execution_id,
                workflow_id,
                inputs,
                status,
                started_at,
                completed_at,
                error
              FROM execution_history
             WHERE execution_id = ?
            """,
            (execution_id,),
        )
        return await cursor.fetchone()

    async def _load_steps(
        self,
        conn: aiosqlite.Connection,
        execution_id: str,
    ) -> list[RunHistoryStep]:
        """Return ordered steps for the execution."""
        cursor = await conn.execute(
            """
            SELECT step_index, at, payload
              FROM execution_history_steps
             WHERE execution_id = ?
             ORDER BY step_index ASC
            """,
            (execution_id,),
        )
        rows = await cursor.fetchall()
        steps: list[RunHistoryStep] = []
        for row in rows:
            steps.append(
                RunHistoryStep(
                    index=row["step_index"],
                    at=datetime.fromisoformat(row["at"]),
                    payload=json.loads(row["payload"]),
                )
            )
        return steps

    def _row_to_record(
        self,
        row: aiosqlite.Row,
        steps: list[RunHistoryStep],
    ) -> RunHistoryRecord:
        """Convert a SQLite row into a RunHistoryRecord instance."""
        completed_at = (
            datetime.fromisoformat(row["completed_at"])
            if row["completed_at"] is not None
            else None
        )
        return RunHistoryRecord(
            workflow_id=row["workflow_id"],
            execution_id=row["execution_id"],
            inputs=json.loads(row["inputs"]),
            status=row["status"],
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=completed_at,
            error=row["error"],
            steps=steps,
        )


__all__ = [
    "InMemoryRunHistoryStore",
    "RunHistoryError",
    "RunHistoryNotFoundError",
    "RunHistoryRecord",
    "RunHistoryStore",
    "RunHistoryStep",
    "SqliteRunHistoryStore",
]
