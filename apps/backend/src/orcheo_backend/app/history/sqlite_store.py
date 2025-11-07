"""SQLite-backed history store shared across backend workers."""

from __future__ import annotations
import asyncio
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
import aiosqlite
from orcheo_backend.app.history.models import (
    RunHistoryError,
    RunHistoryNotFoundError,
    RunHistoryRecord,
    RunHistoryStep,
    _utcnow,
)
from orcheo_backend.app.history.sqlite_utils import (
    INSERT_EXECUTION_SQL,
    INSERT_EXECUTION_STEP_SQL,
    LIST_HISTORIES_SQL,
    SELECT_CURRENT_STEP_INDEX_SQL,
    UPDATE_HISTORY_STATUS_SQL,
    connect_sqlite,
    ensure_sqlite_schema,
    fetch_record_row,
    fetch_steps,
    row_to_record,
)


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
            async with connect_sqlite(self._database_path) as conn:
                try:
                    await conn.execute(
                        INSERT_EXECUTION_SQL,
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
            async with connect_sqlite(self._database_path) as conn:
                record_row = await fetch_record_row(conn, execution_id)
                if record_row is None:
                    msg = f"History not found for execution_id={execution_id}"
                    raise RunHistoryNotFoundError(msg)

                cursor = await conn.execute(
                    SELECT_CURRENT_STEP_INDEX_SQL,
                    (execution_id,),
                )
                row = await cursor.fetchone()
                next_index = (row["current_index"] if row else -1) + 1

                await conn.execute(
                    INSERT_EXECUTION_STEP_SQL,
                    (
                        execution_id,
                        next_index,
                        at.isoformat(),
                        json.dumps(dict(payload)),
                    ),
                )
                await conn.commit()
        return RunHistoryStep(index=next_index, at=at, payload=dict(payload))

    async def mark_completed(self, execution_id: str) -> RunHistoryRecord:
        """Mark the execution as completed."""
        return await self._update_status(execution_id, status="completed", error=None)

    async def mark_failed(
        self,
        execution_id: str,
        error: str,
    ) -> RunHistoryRecord:
        """Mark the execution as failed with the specified error message."""
        return await self._update_status(execution_id, status="error", error=error)

    async def mark_cancelled(
        self,
        execution_id: str,
        *,
        reason: str | None = None,
    ) -> RunHistoryRecord:
        """Mark the execution as cancelled."""
        return await self._update_status(execution_id, status="cancelled", error=reason)

    async def get_history(self, execution_id: str) -> RunHistoryRecord:
        """Return a deep copy of the execution history."""
        await self._ensure_initialized()
        async with connect_sqlite(self._database_path) as conn:
            record_row = await fetch_record_row(conn, execution_id)
            if record_row is None:
                msg = f"History not found for execution_id={execution_id}"
                raise RunHistoryNotFoundError(msg)
            steps = await fetch_steps(conn, execution_id)
            return row_to_record(record_row, steps)

    async def clear(self) -> None:
        """Clear all stored histories. Intended for testing only."""
        await self._ensure_initialized()
        async with self._lock:
            async with connect_sqlite(self._database_path) as conn:
                await conn.execute("DELETE FROM execution_history_steps")
                await conn.execute("DELETE FROM execution_history")
                await conn.commit()

    async def list_histories(
        self,
        workflow_id: str,
        *,
        limit: int | None = None,
    ) -> list[RunHistoryRecord]:
        """Return histories associated with the provided workflow."""
        await self._ensure_initialized()
        query = LIST_HISTORIES_SQL
        params: list[object] = [workflow_id]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        async with connect_sqlite(self._database_path) as conn:
            cursor = await conn.execute(query, tuple(params))
            rows = await cursor.fetchall()
            records: list[RunHistoryRecord] = []
            for row in rows:
                steps = await fetch_steps(conn, row["execution_id"])
                records.append(row_to_record(row, steps))
        return records

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
            async with connect_sqlite(self._database_path) as conn:
                cursor = await conn.execute(
                    UPDATE_HISTORY_STATUS_SQL,
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
                record_row = await fetch_record_row(conn, execution_id)
                if record_row is None:  # pragma: no cover - defensive
                    msg = f"History not found for execution_id={execution_id}"
                    raise RunHistoryNotFoundError(msg)
                steps = await fetch_steps(conn, execution_id)
        record = row_to_record(record_row, steps)
        record.completed_at = completed_at
        record.status = status
        record.error = error
        return record

    async def _ensure_initialized(self) -> None:
        """Create the required tables if they are missing."""
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return
            await ensure_sqlite_schema(self._database_path)
            self._initialized = True


__all__ = ["SqliteRunHistoryStore"]
