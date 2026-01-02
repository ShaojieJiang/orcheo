"""Core utilities shared by the SQLite workflow repository mixins."""

from __future__ import annotations
import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID
import aiosqlite
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


def _parse_optional_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp if present."""
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


class SqliteRepositoryBase:
    """Provide locking, connections, and trigger-layer hydration."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        credential_service: OAuthCredentialService | None = None,
    ) -> None:
        self._database_path = Path(database_path).expanduser()
        self._lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()
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
        if not report.is_healthy:
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

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[aiosqlite.Connection]:
        conn = await aiosqlite.connect(str(self._database_path))
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
            await conn.commit()
        except Exception:  # pragma: no cover - defensive rollback
            await conn.rollback()
            raise
        finally:
            await conn.close()

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            self._database_path.parent.mkdir(parents=True, exist_ok=True)
            async with self._connection() as conn:
                await conn.executescript(
                    """
                    PRAGMA journal_mode=WAL;
                    CREATE TABLE IF NOT EXISTS workflows (
                        id TEXT PRIMARY KEY,
                        payload TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS workflow_versions (
                        id TEXT PRIMARY KEY,
                        workflow_id TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        payload TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(workflow_id, version)
                    );
                    CREATE INDEX IF NOT EXISTS idx_versions_workflow
                        ON workflow_versions(workflow_id);
                    CREATE TABLE IF NOT EXISTS workflow_runs (
                        id TEXT PRIMARY KEY,
                        workflow_id TEXT NOT NULL,
                        workflow_version_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        triggered_by TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_runs_workflow
                        ON workflow_runs(workflow_id);
                    CREATE INDEX IF NOT EXISTS idx_runs_version
                        ON workflow_runs(workflow_version_id);
                    CREATE TABLE IF NOT EXISTS webhook_triggers (
                        workflow_id TEXT PRIMARY KEY,
                        config TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS cron_triggers (
                        workflow_id TEXT PRIMARY KEY,
                        config TEXT NOT NULL,
                        last_dispatched_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS retry_policies (
                        workflow_id TEXT PRIMARY KEY,
                        config TEXT NOT NULL
                    );
                    """
                )
                await self._ensure_cron_schema_migrations(conn)

            await self._hydrate_trigger_state()
            self._initialized = True

    async def _ensure_cron_schema_migrations(self, conn: aiosqlite.Connection) -> None:
        """Add missing columns to cron_triggers table for existing databases."""
        cursor = await conn.execute("PRAGMA table_info(cron_triggers)")
        rows = await cursor.fetchall()
        existing_columns = {row["name"] for row in rows}
        if "last_dispatched_at" not in existing_columns:
            await conn.execute(
                "ALTER TABLE cron_triggers ADD COLUMN last_dispatched_at TEXT"
            )

    async def _hydrate_trigger_state(self) -> None:
        async with self._connection() as conn:
            cursor = await conn.execute(
                "SELECT workflow_id, config FROM retry_policies"
            )
            for row in await cursor.fetchall():
                workflow_id = UUID(row["workflow_id"])
                retry_config = RetryPolicyConfig.model_validate_json(row["config"])
                self._trigger_layer.configure_retry_policy(workflow_id, retry_config)

            cursor = await conn.execute(
                "SELECT workflow_id, config FROM webhook_triggers"
            )
            for row in await cursor.fetchall():
                workflow_id = UUID(row["workflow_id"])
                webhook_config = WebhookTriggerConfig.model_validate_json(row["config"])
                self._trigger_layer.configure_webhook(workflow_id, webhook_config)

            cursor = await conn.execute(
                "SELECT workflow_id, config, last_dispatched_at FROM cron_triggers"
            )
            for row in await cursor.fetchall():
                workflow_id = UUID(row["workflow_id"])
                cron_config = CronTriggerConfig.model_validate_json(row["config"])
                last_dispatched_at = _parse_optional_datetime(row["last_dispatched_at"])
                self._trigger_layer.configure_cron(
                    workflow_id, cron_config, last_dispatched_at=last_dispatched_at
                )

            cursor = await conn.execute(
                """
                SELECT id, workflow_id, triggered_by, status
                  FROM workflow_runs
                 WHERE status IN (?, ?, ?)
                """,
                (
                    WorkflowRunStatus.PENDING.value,
                    WorkflowRunStatus.RUNNING.value,
                    WorkflowRunStatus.FAILED.value,
                ),
            )
            for row in await cursor.fetchall():
                run_id = UUID(row["id"])
                workflow_id = UUID(row["workflow_id"])
                self._trigger_layer.track_run(workflow_id, run_id)
                if row["triggered_by"] == "cron":
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
            config = CronTriggerConfig.model_validate_json(row["config"])
            last_dispatched_at = _parse_optional_datetime(row["last_dispatched_at"])
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
            if state.config.model_dump(mode="json") != config.model_dump(mode="json"):
                self._trigger_layer.configure_cron(
                    workflow_id, config, last_dispatched_at=last_dispatched_at
                )


__all__ = ["SqliteRepositoryBase", "logger"]
