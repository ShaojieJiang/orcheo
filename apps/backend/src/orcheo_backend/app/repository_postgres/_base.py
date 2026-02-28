"""Core utilities shared by the PostgreSQL workflow repository mixins."""

from __future__ import annotations
import asyncio
import importlib
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import UUID
from orcheo.models.workflow import (
    Workflow,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowVersion,
)
from orcheo.triggers.cron import CronTriggerConfig
from orcheo.triggers.layer import TriggerLayer
from orcheo.triggers.retry import RetryPolicyConfig
from orcheo.triggers.webhook import WebhookTriggerConfig
from orcheo.vault.oauth import CredentialHealthError, OAuthCredentialService


logger = logging.getLogger(__name__)


# Optional psycopg dependencies
AsyncConnectionPool: Any | None
DictRowFactory: Any | None

try:  # pragma: no cover - optional dependency
    AsyncConnectionPool = importlib.import_module("psycopg_pool").AsyncConnectionPool
    DictRowFactory = importlib.import_module("psycopg.rows").dict_row
except Exception:  # pragma: no cover - fallback when dependency missing
    AsyncConnectionPool = None
    DictRowFactory = None


POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    handle TEXT,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_versions (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE(workflow_id, version)
);
CREATE INDEX IF NOT EXISTS idx_versions_workflow ON workflow_versions(workflow_id);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    workflow_version_id TEXT NOT NULL,
    status TEXT NOT NULL,
    triggered_by TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_workflow ON workflow_runs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_runs_version ON workflow_runs(workflow_version_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON workflow_runs(status);

CREATE TABLE IF NOT EXISTS webhook_triggers (
    workflow_id TEXT PRIMARY KEY,
    config JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS cron_triggers (
    workflow_id TEXT PRIMARY KEY,
    config JSONB NOT NULL,
    last_dispatched_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS retry_policies (
    workflow_id TEXT PRIMARY KEY,
    config JSONB NOT NULL
);
"""


class PostgresRepositoryBase:
    """Provide connection pooling, schema initialization, trigger-layer hydration."""

    def __init__(
        self,
        dsn: str,
        *,
        credential_service: OAuthCredentialService | None = None,
        pool_min_size: int = 1,
        pool_max_size: int = 10,
        pool_timeout: float = 30.0,
        pool_max_idle: float = 300.0,
    ) -> None:
        if AsyncConnectionPool is None or DictRowFactory is None:
            msg = "PostgreSQL backend requires psycopg[binary,pool] to be installed."
            raise RuntimeError(msg)

        self._dsn = dsn
        self._pool_min_size = pool_min_size
        self._pool_max_size = pool_max_size
        self._pool_timeout = pool_timeout
        self._pool_max_idle = pool_max_idle
        self._pool: Any | None = None
        self._lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()
        self._pool_lock = asyncio.Lock()
        self._initialized = False
        self._credential_service = credential_service
        self._trigger_layer = TriggerLayer(health_guard=credential_service)

    async def _ensure_workflow_health(
        self, workflow_id: UUID, *, actor: str | None = None
    ) -> None:
        if self._credential_service is None:
            return
        report = await self._credential_service.ensure_workflow_health(
            workflow_id, actor=actor
        )
        if not report.is_healthy:  # pragma: no branch
            raise CredentialHealthError(report)

    def _release_cron_run(self, run_id: UUID) -> None:
        self._trigger_layer.release_cron_run(run_id)

    @staticmethod
    def _dump_model(model: Workflow | WorkflowVersion | WorkflowRun) -> str:
        return json.dumps(model.model_dump(mode="json"))

    @staticmethod
    def _dump_config(
        config: WebhookTriggerConfig | CronTriggerConfig | RetryPolicyConfig,
    ) -> str:
        return json.dumps(config.model_dump(mode="json"))

    async def _get_pool(self) -> Any:
        """Return the connection pool, creating it if necessary."""
        if self._pool is not None:
            return self._pool

        async with self._pool_lock:
            if self._pool is not None:
                return self._pool

            # AsyncConnectionPool is verified non-None in __init__
            pool_class = AsyncConnectionPool
            assert pool_class is not None  # mypy
            self._pool = pool_class(
                self._dsn,
                min_size=self._pool_min_size,
                max_size=self._pool_max_size,
                timeout=self._pool_timeout,
                max_idle=self._pool_max_idle,
                open=False,
                kwargs={
                    "autocommit": False,
                    "prepare_threshold": 0,
                    "row_factory": DictRowFactory,
                },
            )
            await self._pool.open()
            return self._pool

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[Any]:
        pool = await self._get_pool()
        async with pool.connection() as conn:
            try:
                yield conn
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            async with self._connection() as conn:
                # Execute schema statements one by one
                for raw_stmt in POSTGRES_SCHEMA.strip().split(";"):
                    stmt = raw_stmt.strip()
                    if stmt:
                        await conn.execute(stmt)
                await self._ensure_cron_schema_migrations(conn)
                await self._ensure_workflow_schema_migrations(conn)

            await self._hydrate_trigger_state()
            self._initialized = True

    async def _ensure_cron_schema_migrations(self, conn: Any) -> None:
        """Add missing columns to cron_triggers table for existing databases."""
        cursor = await conn.execute(
            """
            SELECT column_name
              FROM information_schema.columns
             WHERE table_name = 'cron_triggers'
            """
        )
        rows = await cursor.fetchall()
        existing_columns = {row["column_name"] for row in rows}
        if "last_dispatched_at" not in existing_columns:  # pragma: no branch
            await conn.execute(
                "ALTER TABLE cron_triggers ADD COLUMN last_dispatched_at TIMESTAMPTZ"
            )

    async def _ensure_workflow_schema_migrations(self, conn: Any) -> None:
        """Add mirrored workflow columns and backfill them from payloads."""
        cursor = await conn.execute(
            """
            SELECT column_name
              FROM information_schema.columns
             WHERE table_name = 'workflows'
            """
        )
        rows = await cursor.fetchall()
        existing_columns = {row["column_name"] for row in rows}
        if "handle" not in existing_columns:
            await conn.execute("ALTER TABLE workflows ADD COLUMN handle TEXT")
        if "is_archived" not in existing_columns:
            await conn.execute(
                "ALTER TABLE workflows "
                "ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT FALSE"
            )

        cursor = await conn.execute("SELECT id, payload FROM workflows")
        rows = await cursor.fetchall()
        for row in rows:
            workflow = Workflow.model_validate(row["payload"])
            await conn.execute(
                """
                UPDATE workflows
                   SET handle = %s, is_archived = %s, updated_at = %s
                 WHERE id = %s
                """,
                (
                    workflow.handle,
                    workflow.is_archived,
                    workflow.updated_at,
                    row["id"],
                ),
            )

        # Create indexes after columns are guaranteed to exist
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflows_handle ON workflows(handle)"
        )
        await conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_workflows_active_handle"
            " ON workflows(handle)"
            " WHERE is_archived = FALSE AND handle IS NOT NULL"
        )

    async def _hydrate_trigger_state(self) -> None:
        async with self._connection() as conn:
            cursor = await conn.execute(
                "SELECT workflow_id, config FROM retry_policies"
            )
            rows = await cursor.fetchall()
            for row in rows:
                workflow_id = UUID(row["workflow_id"])
                retry_config = RetryPolicyConfig.model_validate(row["config"])
                self._trigger_layer.configure_retry_policy(workflow_id, retry_config)

            cursor = await conn.execute(
                "SELECT workflow_id, config FROM webhook_triggers"
            )
            rows = await cursor.fetchall()
            for row in rows:
                workflow_id = UUID(row["workflow_id"])
                webhook_config = WebhookTriggerConfig.model_validate(row["config"])
                self._trigger_layer.configure_webhook(workflow_id, webhook_config)

            cursor = await conn.execute(
                "SELECT workflow_id, config, last_dispatched_at FROM cron_triggers"
            )
            rows = await cursor.fetchall()
            for row in rows:
                workflow_id = UUID(row["workflow_id"])
                cron_config = CronTriggerConfig.model_validate(row["config"])
                last_dispatched_at: datetime | None = row["last_dispatched_at"]
                self._trigger_layer.configure_cron(
                    workflow_id, cron_config, last_dispatched_at=last_dispatched_at
                )

            cursor = await conn.execute(
                """
                SELECT id, workflow_id, triggered_by, status
                  FROM workflow_runs
                 WHERE status IN (%s, %s, %s)
                """,
                (
                    WorkflowRunStatus.PENDING.value,
                    WorkflowRunStatus.RUNNING.value,
                    WorkflowRunStatus.FAILED.value,
                ),
            )
            rows = await cursor.fetchall()
            for row in rows:
                run_id = UUID(row["id"])
                workflow_id = UUID(row["workflow_id"])
                self._trigger_layer.track_run(workflow_id, run_id)
                if row["triggered_by"] == "cron":  # pragma: no branch
                    self._trigger_layer.register_cron_run(run_id)

    async def _refresh_cron_triggers(self) -> None:
        """Refresh cron trigger configs to reflect the latest persisted state."""
        async with self._connection() as conn:
            cursor = await conn.execute(
                "SELECT workflow_id, config, last_dispatched_at FROM cron_triggers"
            )
            rows = await cursor.fetchall()

        desired: dict[UUID, tuple[CronTriggerConfig, datetime | None]] = {}
        for row in rows:
            workflow_id = UUID(row["workflow_id"])
            config = CronTriggerConfig.model_validate(row["config"])
            last_dispatched_at: datetime | None = row["last_dispatched_at"]
            desired[workflow_id] = (config, last_dispatched_at)

        current_states = self._trigger_layer._cron_states  # noqa: SLF001
        current_ids = set(current_states)
        desired_ids = set(desired)

        for workflow_id in current_ids - desired_ids:
            self._trigger_layer.remove_cron_config(workflow_id)

        for workflow_id, (config, last_dispatched_at) in desired.items():
            state = current_states.get(workflow_id)
            if state is None:
                self._trigger_layer.configure_cron(
                    workflow_id, config, last_dispatched_at=last_dispatched_at
                )
                continue
            if (
                state.config.model_dump(mode="json") != config.model_dump(mode="json")
                or state.last_dispatched_at != last_dispatched_at
            ):  # pragma: no branch
                self._trigger_layer.configure_cron(
                    workflow_id, config, last_dispatched_at=last_dispatched_at
                )

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None


__all__ = ["PostgresRepositoryBase", "logger"]
