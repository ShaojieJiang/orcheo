"""Persistence backends for Agentensor training checkpoints."""

from __future__ import annotations
import asyncio
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
import aiosqlite
from orcheo.agentensor.checkpoints import (
    AgentensorCheckpoint,
    AgentensorCheckpointNotFoundError,
    AgentensorCheckpointStore,
)
from orcheo_backend.app.history.sqlite_utils import (
    connect_sqlite,
    ensure_sqlite_schema,
)


POSTGRES_CHECKPOINT_MIGRATION = """
CREATE TABLE IF NOT EXISTS agentensor_checkpoints (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    config_version INTEGER NOT NULL,
    runnable_config JSONB NOT NULL,
    metrics JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_url TEXT NULL,
    is_best BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agentensor_checkpoints_workflow
    ON agentensor_checkpoints (workflow_id, config_version);
CREATE INDEX IF NOT EXISTS idx_agentensor_checkpoints_best
    ON agentensor_checkpoints (workflow_id, is_best);
"""


class InMemoryAgentensorCheckpointStore(AgentensorCheckpointStore):
    """Async-safe in-memory checkpoint store."""

    def __init__(self) -> None:
        """Initialize the in-memory store."""
        self._lock = asyncio.Lock()
        self._checkpoints: dict[str, AgentensorCheckpoint] = {}
        self._by_workflow: dict[str, list[str]] = {}

    async def record_checkpoint(
        self,
        *,
        workflow_id: str,
        runnable_config: Mapping[str, object],
        metrics: Mapping[str, object],
        metadata: Mapping[str, object] | None = None,
        artifact_url: str | None = None,
        is_best: bool = False,
        config_version: int | None = None,
    ) -> AgentensorCheckpoint:
        """Persist a checkpoint and return the stored record."""
        async with self._lock:
            version = config_version or self._next_version(workflow_id)
            checkpoint = AgentensorCheckpoint(
                workflow_id=workflow_id,
                config_version=version,
                runnable_config=dict(runnable_config),
                metrics=dict(metrics),
                metadata=dict(metadata or {}),
                artifact_url=artifact_url,
                is_best=is_best,
            )
            self._checkpoints[checkpoint.id] = checkpoint
            self._by_workflow.setdefault(workflow_id, []).append(checkpoint.id)
            if is_best:
                self._clear_other_best(workflow_id, checkpoint.id)
            return checkpoint

    async def list_checkpoints(
        self,
        workflow_id: str,
        *,
        limit: int | None = None,
    ) -> list[AgentensorCheckpoint]:
        """Return checkpoints for the workflow ordered newest-first."""
        async with self._lock:
            identifiers = list(reversed(self._by_workflow.get(workflow_id, [])))
            if limit is not None:
                identifiers = identifiers[:limit]
            return [self._checkpoints[identifier] for identifier in identifiers]

    async def get_checkpoint(self, checkpoint_id: str) -> AgentensorCheckpoint:
        """Return the checkpoint by identifier or raise when missing."""
        async with self._lock:
            checkpoint = self._checkpoints.get(checkpoint_id)
            if checkpoint is None:
                msg = f"Checkpoint {checkpoint_id!r} not found."
                raise AgentensorCheckpointNotFoundError(msg)
            return checkpoint

    async def latest_checkpoint(
        self,
        workflow_id: str,
    ) -> AgentensorCheckpoint | None:
        """Return the most recent checkpoint for the workflow if present."""
        async with self._lock:
            identifiers = self._by_workflow.get(workflow_id, [])
            if not identifiers:
                return None
            return self._checkpoints[identifiers[-1]]

    def _next_version(self, workflow_id: str) -> int:
        identifiers = self._by_workflow.get(workflow_id, [])
        if not identifiers:
            return 1
        latest = self._checkpoints[identifiers[-1]]
        return latest.config_version + 1

    def _clear_other_best(self, workflow_id: str, checkpoint_id: str) -> None:
        for identifier in self._by_workflow.get(workflow_id, []):
            if identifier == checkpoint_id:
                continue
            checkpoint = self._checkpoints.get(identifier)
            if checkpoint is None:
                continue
            checkpoint.is_best = False


class SqliteAgentensorCheckpointStore(AgentensorCheckpointStore):
    """SQLite-backed checkpoint store shared across backend workers."""

    def __init__(self, database_path: str | Path) -> None:
        """Initialize the SQLite store with the given database path."""
        self._database_path = Path(database_path).expanduser()
        self._lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def record_checkpoint(
        self,
        *,
        workflow_id: str,
        runnable_config: Mapping[str, object],
        metrics: Mapping[str, object],
        metadata: Mapping[str, object] | None = None,
        artifact_url: str | None = None,
        is_best: bool = False,
        config_version: int | None = None,
    ) -> AgentensorCheckpoint:
        """Persist a checkpoint row and return the stored domain object."""
        await self._ensure_initialized()
        async with self._lock:
            async with connect_sqlite(self._database_path) as conn:
                await conn.execute("BEGIN")
                try:
                    version = await self._resolve_version(
                        conn, workflow_id, config_version
                    )
                    checkpoint = AgentensorCheckpoint(
                        workflow_id=workflow_id,
                        config_version=version,
                        runnable_config=dict(runnable_config),
                        metrics=dict(metrics),
                        metadata=dict(metadata or {}),
                        artifact_url=artifact_url,
                        is_best=is_best,
                    )
                    await conn.execute(
                        """
                        INSERT INTO agentensor_checkpoints (
                            id,
                            workflow_id,
                            config_version,
                            runnable_config,
                            metrics,
                            metadata,
                            artifact_url,
                            is_best,
                            created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            checkpoint.id,
                            checkpoint.workflow_id,
                            checkpoint.config_version,
                            json.dumps(checkpoint.runnable_config),
                            json.dumps(checkpoint.metrics),
                            json.dumps(checkpoint.metadata),
                            checkpoint.artifact_url,
                            1 if checkpoint.is_best else 0,
                            checkpoint.created_at.isoformat(),
                        ),
                    )
                    if is_best:
                        await conn.execute(
                            """
                            UPDATE agentensor_checkpoints
                               SET is_best = 0
                             WHERE workflow_id = ?
                               AND id != ?
                            """,
                            (workflow_id, checkpoint.id),
                        )
                    await conn.commit()
                except Exception:
                    await conn.rollback()
                    raise
                return checkpoint

    async def list_checkpoints(
        self,
        workflow_id: str,
        *,
        limit: int | None = None,
    ) -> list[AgentensorCheckpoint]:
        """Return persisted checkpoints ordered by config_version."""
        await self._ensure_initialized()
        query = (
            "SELECT id, workflow_id, config_version, runnable_config, metrics, "
            "metadata, artifact_url, is_best, created_at "
            "FROM agentensor_checkpoints WHERE workflow_id = ? "
            "ORDER BY config_version DESC"
        )
        params: list[object] = [workflow_id]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        async with connect_sqlite(self._database_path) as conn:
            cursor = await conn.execute(query, tuple(params))
            rows = await cursor.fetchall()
        return [self._row_to_checkpoint(row) for row in rows]

    async def get_checkpoint(self, checkpoint_id: str) -> AgentensorCheckpoint:
        """Return a checkpoint by identifier or raise when missing."""
        await self._ensure_initialized()
        async with connect_sqlite(self._database_path) as conn:
            cursor = await conn.execute(
                """
                SELECT id, workflow_id, config_version, runnable_config, metrics,
                       metadata, artifact_url, is_best, created_at
                  FROM agentensor_checkpoints
                 WHERE id = ?
                """,
                (checkpoint_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            msg = f"Checkpoint {checkpoint_id!r} not found."
            raise AgentensorCheckpointNotFoundError(msg)
        return self._row_to_checkpoint(row)

    async def latest_checkpoint(
        self,
        workflow_id: str,
    ) -> AgentensorCheckpoint | None:
        """Return the newest checkpoint if one exists for the workflow."""
        checkpoints = await self.list_checkpoints(workflow_id, limit=1)
        return checkpoints[0] if checkpoints else None

    async def _resolve_version(
        self,
        conn: aiosqlite.Connection,
        workflow_id: str,
        provided_version: int | None,
    ) -> int:
        """Resolve the next config version for the workflow."""
        if provided_version is not None:
            return provided_version
        cursor = await conn.execute(
            """
            SELECT COALESCE(MAX(config_version), 0) AS max_version
              FROM agentensor_checkpoints
             WHERE workflow_id = ?
            """,
            (workflow_id,),
        )
        row = await cursor.fetchone()
        max_version = row["max_version"] if row else 0
        return int(max_version) + 1

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            await ensure_sqlite_schema(self._database_path)
            self._initialized = True

    @staticmethod
    def _row_to_checkpoint(row: aiosqlite.Row) -> AgentensorCheckpoint:
        return AgentensorCheckpoint(
            id=row["id"],
            workflow_id=row["workflow_id"],
            config_version=int(row["config_version"]),
            runnable_config=json.loads(row["runnable_config"]),
            metrics=json.loads(row["metrics"]),
            metadata=json.loads(row["metadata"]),
            artifact_url=row["artifact_url"],
            is_best=bool(row["is_best"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )


__all__ = [
    "AgentensorCheckpointNotFoundError",
    "InMemoryAgentensorCheckpointStore",
    "POSTGRES_CHECKPOINT_MIGRATION",
    "SqliteAgentensorCheckpointStore",
]
