"""SQLite-backed implementation for service token persistence."""

from __future__ import annotations
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from orcheo_backend.app.authentication import ServiceTokenRecord
from .protocol import ServiceTokenRepository


class SqliteServiceTokenRepository(ServiceTokenRepository):
    """SQLite-backed implementation of ServiceTokenRepository."""

    def __init__(self, db_path: str | Path) -> None:
        """Initialize the repository with the database path."""
        self._db_path = Path(db_path).expanduser()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS service_tokens (
                    identifier TEXT PRIMARY KEY,
                    secret_hash TEXT NOT NULL,
                    scopes TEXT,
                    workspace_ids TEXT,
                    created_at TEXT NOT NULL,
                    created_by TEXT,
                    issued_at TEXT,
                    expires_at TEXT,
                    last_used_at TEXT,
                    use_count INTEGER DEFAULT 0,
                    rotation_expires_at TEXT,
                    rotated_to TEXT,
                    rotated_from TEXT,
                    revoked_at TEXT,
                    revoked_by TEXT,
                    revocation_reason TEXT,
                    allowed_ip_ranges TEXT,
                    rate_limit_override INTEGER,
                    FOREIGN KEY (rotated_to) REFERENCES service_tokens(identifier)
                );

                CREATE INDEX IF NOT EXISTS idx_service_tokens_hash
                    ON service_tokens(secret_hash);
                CREATE INDEX IF NOT EXISTS idx_service_tokens_expires
                    ON service_tokens(expires_at);
                CREATE INDEX IF NOT EXISTS idx_service_tokens_active
                    ON service_tokens(revoked_at) WHERE revoked_at IS NULL;

                CREATE TABLE IF NOT EXISTS service_token_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    timestamp TEXT NOT NULL,
                    details TEXT,
                    FOREIGN KEY (token_id) REFERENCES service_tokens(identifier)
                );

                CREATE INDEX IF NOT EXISTS idx_audit_log_token
                    ON service_token_audit_log(token_id);
                CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp
                    ON service_token_audit_log(timestamp);
                """
            )

    async def list_all(self) -> list[ServiceTokenRecord]:
        """Return all service token records."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM service_tokens ORDER BY created_at DESC"
            )
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]

    async def list_active(
        self, *, now: datetime | None = None
    ) -> list[ServiceTokenRecord]:
        """Return all active service token records."""
        reference = (now or datetime.now(tz=UTC)).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM service_tokens
                WHERE revoked_at IS NULL
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY created_at DESC
                """,
                (reference,),
            )
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]

    async def find_by_id(self, identifier: str) -> ServiceTokenRecord | None:
        """Look up a service token by identifier."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM service_tokens WHERE identifier = ?", (identifier,)
            )
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None

    async def find_by_hash(self, secret_hash: str) -> ServiceTokenRecord | None:
        """Look up a service token by its SHA256 hash."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM service_tokens WHERE secret_hash = ?", (secret_hash,)
            )
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None

    async def create(self, record: ServiceTokenRecord) -> ServiceTokenRecord:
        """Store a new service token record."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO service_tokens (
                    identifier, secret_hash, scopes, workspace_ids,
                    created_at, created_by, issued_at, expires_at,
                    rotation_expires_at, rotated_to, revoked_at,
                    revoked_by, revocation_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.identifier,
                    record.secret_hash,
                    json.dumps(sorted(record.scopes)) if record.scopes else None,
                    json.dumps(sorted(record.workspace_ids))
                    if record.workspace_ids
                    else None,
                    datetime.now(tz=UTC).isoformat(),
                    None,
                    record.issued_at.isoformat() if record.issued_at else None,
                    record.expires_at.isoformat() if record.expires_at else None,
                    record.rotation_expires_at.isoformat()
                    if record.rotation_expires_at
                    else None,
                    record.rotated_to,
                    record.revoked_at.isoformat() if record.revoked_at else None,
                    None,
                    record.revocation_reason,
                ),
            )
            conn.commit()
        return record

    async def update(self, record: ServiceTokenRecord) -> ServiceTokenRecord:
        """Update an existing service token record."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                UPDATE service_tokens
                SET secret_hash = ?,
                    scopes = ?,
                    workspace_ids = ?,
                    issued_at = ?,
                    expires_at = ?,
                    rotation_expires_at = ?,
                    rotated_to = ?,
                    revoked_at = ?,
                    revocation_reason = ?
                WHERE identifier = ?
                """,
                (
                    record.secret_hash,
                    json.dumps(sorted(record.scopes)) if record.scopes else None,
                    json.dumps(sorted(record.workspace_ids))
                    if record.workspace_ids
                    else None,
                    record.issued_at.isoformat() if record.issued_at else None,
                    record.expires_at.isoformat() if record.expires_at else None,
                    record.rotation_expires_at.isoformat()
                    if record.rotation_expires_at
                    else None,
                    record.rotated_to,
                    record.revoked_at.isoformat() if record.revoked_at else None,
                    record.revocation_reason,
                    record.identifier,
                ),
            )
            conn.commit()
        return record

    async def delete(self, identifier: str) -> None:
        """Remove a service token from storage."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "DELETE FROM service_tokens WHERE identifier = ?", (identifier,)
            )
            conn.commit()

    async def record_usage(
        self,
        token_id: str,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Track token usage."""
        now = datetime.now(tz=UTC).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                UPDATE service_tokens
                SET last_used_at = ?,
                    use_count = use_count + 1
                WHERE identifier = ?
                """,
                (now, token_id),
            )
            details: dict[str, Any] = {}
            if ip:
                details["ip"] = ip
            if user_agent:
                details["user_agent"] = user_agent
            conn.execute(
                """
                INSERT INTO service_token_audit_log
                    (token_id, action, ip_address, user_agent, timestamp, details)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    token_id,
                    "used",
                    ip,
                    user_agent,
                    now,
                    json.dumps(details) if details else None,
                ),
            )
            conn.commit()

    async def get_audit_log(
        self, token_id: str, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Retrieve audit log entries for a token."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM service_token_audit_log
                WHERE token_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (token_id, limit),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    async def record_audit_event(
        self,
        token_id: str,
        action: str,
        *,
        actor: str | None = None,
        ip: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record an audit event for a token."""
        now = datetime.now(tz=UTC).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO service_token_audit_log
                    (token_id, action, actor, ip_address, timestamp, details)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    token_id,
                    action,
                    actor,
                    ip,
                    now,
                    json.dumps(details) if details else None,
                ),
            )
            conn.commit()

    def _row_to_record(self, row: sqlite3.Row) -> ServiceTokenRecord:
        """Convert a database row to a ServiceTokenRecord."""
        scopes_json = row["scopes"]
        workspace_ids_json = row["workspace_ids"]
        return ServiceTokenRecord(
            identifier=row["identifier"],
            secret_hash=row["secret_hash"],
            scopes=frozenset(json.loads(scopes_json)) if scopes_json else frozenset(),
            workspace_ids=frozenset(json.loads(workspace_ids_json))
            if workspace_ids_json
            else frozenset(),
            issued_at=self._parse_timestamp(row["issued_at"]),
            expires_at=self._parse_timestamp(row["expires_at"]),
            rotation_expires_at=self._parse_timestamp(row["rotation_expires_at"]),
            revoked_at=self._parse_timestamp(row["revoked_at"]),
            revocation_reason=row["revocation_reason"],
            rotated_to=row["rotated_to"],
            last_used_at=self._parse_timestamp(row["last_used_at"]),
            use_count=int(row["use_count"]) if row["use_count"] is not None else 0,
        )

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime | None:
        """Parse ISO timestamp string to datetime."""
        if not value:
            return None
        return datetime.fromisoformat(value)


__all__ = ["SqliteServiceTokenRepository"]
