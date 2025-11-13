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
    root_span_id TEXT
);
CREATE TABLE IF NOT EXISTS execution_history_steps (
    execution_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    at TEXT NOT NULL,
    payload TEXT NOT NULL,
    trace_id TEXT,
    span_id TEXT,
    parent_span_id TEXT,
    span_name TEXT,
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
    root_span_id
)
VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?)
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
    payload,
    trace_id,
    span_id,
    parent_span_id,
    span_name
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""

LIST_HISTORIES_SQL = (
    "SELECT execution_id, workflow_id, inputs, status, "
    "started_at, completed_at, error, "
    "trace_id, root_span_id "
    "FROM execution_history "
    "WHERE workflow_id = ? "
    "ORDER BY started_at DESC"
)

UPDATE_HISTORY_STATUS_SQL = """
UPDATE execution_history
   SET status = ?,
       completed_at = ?,
       error = ?
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
        await _ensure_column(conn, "execution_history", "trace_id", "TEXT")
        await _ensure_column(conn, "execution_history", "root_span_id", "TEXT")
        await _ensure_column(conn, "execution_history_steps", "trace_id", "TEXT")
        await _ensure_column(conn, "execution_history_steps", "span_id", "TEXT")
        await _ensure_column(conn, "execution_history_steps", "parent_span_id", "TEXT")
        await _ensure_column(conn, "execution_history_steps", "span_name", "TEXT")
        await conn.commit()


async def fetch_record_row(
    conn: aiosqlite.Connection,
    execution_id: str,
) -> aiosqlite.Row | None:
    """Return the raw execution history row if present."""
    cursor = await conn.execute(
        """
        SELECT execution_id, workflow_id, inputs, status, started_at,
               completed_at, error, trace_id, root_span_id
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
        SELECT step_index, at, payload, trace_id, span_id, parent_span_id, span_name
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
                trace_id=row["trace_id"],
                span_id=row["span_id"],
                parent_span_id=row["parent_span_id"],
                span_name=row["span_name"],
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
    )


async def _ensure_column(
    conn: aiosqlite.Connection, table: str, column: str, definition: str
) -> None:
    """Ensure the provided column exists on the SQLite table."""
    cursor = await conn.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    existing = {row["name"] for row in rows}
    if column in existing:
        return
    await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


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
