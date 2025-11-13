"""Shared helpers for the SQLite run history store."""

from __future__ import annotations
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
import aiosqlite
from orcheo_backend.app.history.models import RunHistoryRecord, RunHistoryStep


SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS execution_history (
    execution_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    inputs TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT,
    trace_id TEXT,
    root_span_id TEXT,
    trace_started_at TEXT,
    trace_completed_at TEXT
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

INSERT_EXECUTION_SQL = """
INSERT INTO execution_history (
    execution_id,
    workflow_id,
    inputs,
    status,
    started_at,
    completed_at,
    error,
    trace_id,
    root_span_id,
    trace_started_at,
    trace_completed_at
)
VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, NULL)
"""

SELECT_CURRENT_STEP_INDEX_SQL = """
SELECT COALESCE(MAX(step_index), -1) AS current_index
  FROM execution_history_steps
 WHERE execution_id = ?
"""

INSERT_EXECUTION_STEP_SQL = """
INSERT INTO execution_history_steps (
    execution_id,
    step_index,
    at,
    payload
)
VALUES (?, ?, ?, ?)
"""

LIST_HISTORIES_SQL = (
    "SELECT execution_id, workflow_id, inputs, status, started_at, completed_at, "
    "error, trace_id, root_span_id, trace_started_at, trace_completed_at "
    "FROM execution_history WHERE workflow_id = ? ORDER BY started_at DESC"
)

UPDATE_HISTORY_STATUS_SQL = """
UPDATE execution_history
   SET status = ?,
       completed_at = ?,
       error = ?,
       trace_completed_at = ?
 WHERE execution_id = ?
"""


@asynccontextmanager
async def connect_sqlite(database_path: Path) -> AsyncIterator[aiosqlite.Connection]:
    """Yield a configured SQLite connection for the history database."""
    conn = await aiosqlite.connect(database_path)
    try:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
    finally:
        await conn.close()


async def ensure_sqlite_schema(database_path: Path) -> None:
    """Create the history tables when the database is initialised."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    async with connect_sqlite(database_path) as conn:
        await conn.executescript(SCHEMA_SQL)
        for statement in (
            "ALTER TABLE execution_history ADD COLUMN trace_id TEXT",
            "ALTER TABLE execution_history ADD COLUMN root_span_id TEXT",
            "ALTER TABLE execution_history ADD COLUMN trace_started_at TEXT",
            "ALTER TABLE execution_history ADD COLUMN trace_completed_at TEXT",
        ):
            try:
                await conn.execute(statement)
            except aiosqlite.OperationalError as exc:  # pragma: no cover - defensive
                if "duplicate column name" not in str(exc).lower():
                    raise
        await conn.commit()


async def fetch_record_row(
    conn: aiosqlite.Connection,
    execution_id: str,
) -> aiosqlite.Row | None:
    """Return the raw execution history row if present."""
    cursor = await conn.execute(
        """
        SELECT execution_id, workflow_id, inputs, status, started_at,
               completed_at, error, trace_id, root_span_id,
               trace_started_at, trace_completed_at
          FROM execution_history
         WHERE execution_id = ?
        """,
        (execution_id,),
    )
    return await cursor.fetchone()


async def fetch_steps(
    conn: aiosqlite.Connection,
    execution_id: str,
) -> list[RunHistoryStep]:
    """Return ordered steps for the provided execution."""
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


def row_to_record(
    row: aiosqlite.Row,
    steps: list[RunHistoryStep],
) -> RunHistoryRecord:
    """Convert a SQLite row into a RunHistoryRecord instance."""
    completed_at = (
        datetime.fromisoformat(row["completed_at"])
        if row["completed_at"] is not None
        else None
    )
    trace_started_at = (
        datetime.fromisoformat(row["trace_started_at"])
        if row["trace_started_at"] is not None
        else None
    )
    trace_completed_at = (
        datetime.fromisoformat(row["trace_completed_at"])
        if row["trace_completed_at"] is not None
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
        trace_id=row["trace_id"],
        root_span_id=row["root_span_id"],
        trace_started_at=trace_started_at,
        trace_completed_at=trace_completed_at,
    )


__all__ = [
    "INSERT_EXECUTION_SQL",
    "INSERT_EXECUTION_STEP_SQL",
    "LIST_HISTORIES_SQL",
    "SCHEMA_SQL",
    "SELECT_CURRENT_STEP_INDEX_SQL",
    "UPDATE_HISTORY_STATUS_SQL",
    "connect_sqlite",
    "ensure_sqlite_schema",
    "fetch_record_row",
    "fetch_steps",
    "row_to_record",
]
