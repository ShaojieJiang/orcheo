"""SQLite connection and schema helpers for credential vaults."""

from __future__ import annotations
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from queue import Empty, Full, LifoQueue


_CREATE_CREDENTIALS_TABLE = """
CREATE TABLE IF NOT EXISTS credentials (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload TEXT NOT NULL
)
"""

_CREATE_CREDENTIALS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_credentials_workflow
    ON credentials(workflow_id)
"""

_CREATE_TEMPLATES_TABLE = """
CREATE TABLE IF NOT EXISTS credential_templates (
    id TEXT PRIMARY KEY,
    scope_hint TEXT NOT NULL,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload TEXT NOT NULL
)
"""

_CREATE_TEMPLATES_INDEX = """
CREATE INDEX IF NOT EXISTS idx_templates_scope
    ON credential_templates(scope_hint)
"""

_CREATE_ALERTS_TABLE = """
CREATE TABLE IF NOT EXISTS governance_alerts (
    id TEXT PRIMARY KEY,
    scope_hint TEXT NOT NULL,
    acknowledged INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload TEXT NOT NULL
)
"""

_CREATE_ALERTS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_alerts_scope
    ON governance_alerts(scope_hint)
"""


class SQLiteConnectionMixin:
    """Mixin encapsulating SQLite connection pooling and schema setup."""

    def __init__(self, path: str | Path) -> None:
        """Construct the connection pool and ensure schema initialization."""
        self._path = Path(path).expanduser()
        self._lock = threading.Lock()
        self._connection_pool: LifoQueue[sqlite3.Connection] = LifoQueue(maxsize=5)
        self._initialize()

    def _initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._create_connection()
        try:
            conn.execute(_CREATE_CREDENTIALS_TABLE)
            conn.execute(_CREATE_CREDENTIALS_INDEX)
            conn.execute(_CREATE_TEMPLATES_TABLE)
            conn.execute(_CREATE_TEMPLATES_INDEX)
            conn.execute(_CREATE_ALERTS_TABLE)
            conn.execute(_CREATE_ALERTS_INDEX)
            conn.commit()
        finally:
            self._release_connection(conn)

    def _create_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(
            self._path,
            check_same_thread=False,
            timeout=30.0,
        )

    def _release_connection(self, conn: sqlite3.Connection) -> None:
        if conn.in_transaction:
            conn.rollback()
        try:
            self._connection_pool.put_nowait(conn)
        except Full:
            conn.close()

    @contextmanager
    def _acquire_connection(self) -> Iterator[sqlite3.Connection]:
        try:
            conn = self._connection_pool.get_nowait()
        except Empty:
            conn = self._create_connection()
        try:
            yield conn
        finally:
            self._release_connection(conn)

    @contextmanager
    def _locked_connection(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            with self._acquire_connection() as conn:
                yield conn


__all__ = ["SQLiteConnectionMixin"]
