"""SQLite-backed workflow repository implementation."""

from __future__ import annotations
import asyncio
import json
from collections.abc import AsyncIterator, Callable, Iterable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from difflib import unified_diff
from pathlib import Path
from typing import Any
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
from orcheo.triggers.manual import ManualDispatchRequest
from orcheo.triggers.retry import RetryDecision, RetryPolicyConfig
from orcheo.triggers.webhook import WebhookRequest, WebhookTriggerConfig
from orcheo.vault.oauth import CredentialHealthError, OAuthCredentialService
from orcheo_backend.app.repository import (
    VersionDiff,
    WorkflowNotFoundError,
    WorkflowRunNotFoundError,
    WorkflowVersionNotFoundError,
)


class SqliteWorkflowRepository:
    """SQLite-backed workflow repository for durable local development state."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        credential_service: OAuthCredentialService | None = None,
    ) -> None:
        """Initialize the repository with the SQLite database path."""
        self._database_path = Path(database_path).expanduser()
        self._lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()
        self._initialized = False
        self._credential_service = credential_service
        self._trigger_layer = TriggerLayer(health_guard=credential_service)

    async def list_workflows(self) -> list[Workflow]:
        """Return all persisted workflows."""
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                cursor = await conn.execute(
                    "SELECT payload FROM workflows ORDER BY created_at ASC"
                )
                rows = await cursor.fetchall()
            return [
                Workflow.model_validate_json(row["payload"]).model_copy(deep=True)
                for row in rows
            ]

    async def create_workflow(
        self,
        *,
        name: str,
        slug: str | None,
        description: str | None,
        tags: Iterable[str] | None,
        actor: str,
    ) -> Workflow:
        """Create and return a new workflow record."""
        await self._ensure_initialized()
        async with self._lock:
            workflow = Workflow(
                name=name,
                slug=slug or "",
                description=description,
                tags=list(tags or []),
            )
            workflow.record_event(actor=actor, action="workflow_created")
            async with self._connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO workflows (id, payload, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        str(workflow.id),
                        self._dump_model(workflow),
                        workflow.created_at.isoformat(),
                        workflow.updated_at.isoformat(),
                    ),
                )
            return workflow.model_copy(deep=True)

    async def get_workflow(self, workflow_id: UUID) -> Workflow:
        """Return a workflow by identifier."""
        await self._ensure_initialized()
        async with self._lock:
            return await self._get_workflow_locked(workflow_id)

    async def update_workflow(
        self,
        workflow_id: UUID,
        *,
        name: str | None,
        description: str | None,
        tags: Iterable[str] | None,
        is_archived: bool | None,
        actor: str,
    ) -> Workflow:
        """Update workflow metadata and return the modified record."""
        await self._ensure_initialized()
        async with self._lock:
            workflow = await self._get_workflow_locked(workflow_id)

            metadata: dict[str, Any] = {}

            if name is not None and name != workflow.name:
                metadata["name"] = {"from": workflow.name, "to": name}
                workflow.name = name

            if description is not None and description != workflow.description:
                metadata["description"] = {
                    "from": workflow.description,
                    "to": description,
                }
                workflow.description = description

            if tags is not None:
                normalized_tags = list(tags)
                if normalized_tags != workflow.tags:
                    metadata["tags"] = {"from": workflow.tags, "to": normalized_tags}
                    workflow.tags = normalized_tags

            if is_archived is not None and is_archived != workflow.is_archived:
                metadata["is_archived"] = {
                    "from": workflow.is_archived,
                    "to": is_archived,
                }
                workflow.is_archived = is_archived

            workflow.record_event(
                actor=actor,
                action="workflow_updated",
                metadata=metadata,
            )

            async with self._connection() as conn:
                await conn.execute(
                    """
                    UPDATE workflows
                       SET payload = ?, updated_at = ?
                     WHERE id = ?
                    """,
                    (
                        self._dump_model(workflow),
                        workflow.updated_at.isoformat(),
                        str(workflow.id),
                    ),
                )
            return workflow.model_copy(deep=True)

    async def archive_workflow(self, workflow_id: UUID, *, actor: str) -> Workflow:
        """Archive the specified workflow."""
        return await self.update_workflow(
            workflow_id,
            name=None,
            description=None,
            tags=None,
            is_archived=True,
            actor=actor,
        )

    async def create_version(
        self,
        workflow_id: UUID,
        *,
        graph: dict[str, Any],
        metadata: dict[str, Any],
        notes: str | None,
        created_by: str,
    ) -> WorkflowVersion:
        """Create and return a workflow version for the workflow."""
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            async with self._connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT COALESCE(MAX(version), 0)
                      FROM workflow_versions
                     WHERE workflow_id = ?
                    """,
                    (str(workflow_id),),
                )
                row = await cursor.fetchone()
                max_version = int(row[0]) if row and row[0] is not None else 0
                next_version_number = max_version + 1

                version = WorkflowVersion(
                    workflow_id=workflow_id,
                    version=next_version_number,
                    graph=json.loads(json.dumps(graph)),
                    metadata=dict(metadata),
                    created_by=created_by,
                    notes=notes,
                )
                version.record_event(actor=created_by, action="version_created")

                await conn.execute(
                    """
                    INSERT INTO workflow_versions (
                        id,
                        workflow_id,
                        version,
                        payload,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(version.id),
                        str(workflow_id),
                        version.version,
                        self._dump_model(version),
                        version.created_at.isoformat(),
                        version.updated_at.isoformat(),
                    ),
                )
            return version.model_copy(deep=True)

    async def list_versions(self, workflow_id: UUID) -> list[WorkflowVersion]:
        """Return ordered workflow versions for the workflow."""
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            async with self._connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT payload
                      FROM workflow_versions
                     WHERE workflow_id = ?
                  ORDER BY version ASC
                    """,
                    (str(workflow_id),),
                )
                rows = await cursor.fetchall()
            return [
                WorkflowVersion.model_validate_json(row["payload"]).model_copy(
                    deep=True
                )
                for row in rows
            ]

    async def get_version_by_number(
        self, workflow_id: UUID, version_number: int
    ) -> WorkflowVersion:
        """Return a workflow version by number."""
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            async with self._connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT payload
                      FROM workflow_versions
                     WHERE workflow_id = ? AND version = ?
                    """,
                    (str(workflow_id), version_number),
                )
                row = await cursor.fetchone()
                if row is None:
                    raise WorkflowVersionNotFoundError(f"v{version_number}")
            return WorkflowVersion.model_validate_json(row["payload"]).model_copy(
                deep=True
            )

    async def get_version(self, version_id: UUID) -> WorkflowVersion:
        """Return a workflow version by identifier."""
        await self._ensure_initialized()
        async with self._lock:
            return await self._get_version_locked(version_id)

    async def get_latest_version(self, workflow_id: UUID) -> WorkflowVersion:
        """Return the most recent version for the workflow."""
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            async with self._connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT payload
                      FROM workflow_versions
                     WHERE workflow_id = ?
                  ORDER BY version DESC
                     LIMIT 1
                    """,
                    (str(workflow_id),),
                )
                row = await cursor.fetchone()
                if row is None:
                    raise WorkflowVersionNotFoundError("latest")
            return WorkflowVersion.model_validate_json(row["payload"]).model_copy(
                deep=True
            )

    async def diff_versions(
        self, workflow_id: UUID, base_version: int, target_version: int
    ) -> VersionDiff:
        """Return a unified diff between two workflow versions."""
        base = await self.get_version_by_number(workflow_id, base_version)
        target = await self.get_version_by_number(workflow_id, target_version)

        base_serialized = json.dumps(base.graph, indent=2, sort_keys=True).splitlines()
        target_serialized = json.dumps(
            target.graph,
            indent=2,
            sort_keys=True,
        ).splitlines()

        diff = list(
            unified_diff(
                base_serialized,
                target_serialized,
                fromfile=f"v{base_version}",
                tofile=f"v{target_version}",
                lineterm="",
            )
        )
        return VersionDiff(
            base_version=base_version,
            target_version=target_version,
            diff=diff,
        )

    async def create_run(
        self,
        workflow_id: UUID,
        *,
        workflow_version_id: UUID,
        triggered_by: str,
        input_payload: dict[str, Any],
        actor: str | None = None,
    ) -> WorkflowRun:
        """Create and return a workflow run."""
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            await self._ensure_workflow_health(workflow_id, actor=actor or triggered_by)
            run = await self._create_run_locked(
                workflow_id=workflow_id,
                workflow_version_id=workflow_version_id,
                triggered_by=triggered_by,
                input_payload=input_payload,
                actor=actor,
            )
            return run.model_copy(deep=True)

    async def list_runs_for_workflow(self, workflow_id: UUID) -> list[WorkflowRun]:
        """Return runs associated with the workflow."""
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            async with self._connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT payload
                      FROM workflow_runs
                     WHERE workflow_id = ?
                  ORDER BY created_at ASC
                    """,
                    (str(workflow_id),),
                )
                rows = await cursor.fetchall()
            return [
                WorkflowRun.model_validate_json(row["payload"]).model_copy(deep=True)
                for row in rows
            ]

    async def get_run(self, run_id: UUID) -> WorkflowRun:
        """Return a workflow run by identifier."""
        await self._ensure_initialized()
        async with self._lock:
            return await self._get_run_locked(run_id)

    async def mark_run_started(self, run_id: UUID, *, actor: str) -> WorkflowRun:
        """Mark a run as started."""
        return await self._update_run(run_id, lambda run: run.mark_started(actor=actor))

    async def mark_run_succeeded(
        self,
        run_id: UUID,
        *,
        actor: str,
        output: dict[str, Any] | None,
    ) -> WorkflowRun:
        """Mark a run as succeeded with optional output payload."""
        run = await self._update_run(
            run_id,
            lambda run: run.mark_succeeded(actor=actor, output=output),
        )
        self._release_cron_run(run_id)
        self._trigger_layer.clear_retry_state(run_id)
        return run

    async def mark_run_failed(
        self,
        run_id: UUID,
        *,
        actor: str,
        error: str,
    ) -> WorkflowRun:
        """Mark a run as failed."""
        run = await self._update_run(
            run_id,
            lambda run: run.mark_failed(actor=actor, error=error),
        )
        self._release_cron_run(run_id)
        return run

    async def mark_run_cancelled(
        self,
        run_id: UUID,
        *,
        actor: str,
        reason: str | None,
    ) -> WorkflowRun:
        """Cancel a run with an optional reason."""
        run = await self._update_run(
            run_id,
            lambda run: run.mark_cancelled(actor=actor, reason=reason),
        )
        self._release_cron_run(run_id)
        self._trigger_layer.clear_retry_state(run_id)
        return run

    async def reset(self) -> None:
        """Clear all persisted workflows, versions, runs, and trigger state."""
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                await conn.executescript(
                    """
                    DELETE FROM workflow_runs;
                    DELETE FROM workflow_versions;
                    DELETE FROM workflows;
                    DELETE FROM webhook_triggers;
                    DELETE FROM cron_triggers;
                    DELETE FROM retry_policies;
                    """
                )
            self._trigger_layer.reset()

    async def configure_webhook_trigger(
        self, workflow_id: UUID, config: WebhookTriggerConfig
    ) -> WebhookTriggerConfig:
        """Persist webhook trigger configuration for the workflow."""
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            normalized = self._trigger_layer.configure_webhook(workflow_id, config)
            async with self._connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO webhook_triggers (workflow_id, config)
                    VALUES (?, ?)
                    ON CONFLICT(workflow_id) DO UPDATE SET config=excluded.config
                    """,
                    (str(workflow_id), self._dump_config(normalized)),
                )
            return normalized.model_copy(deep=True)

    async def get_webhook_trigger_config(
        self, workflow_id: UUID
    ) -> WebhookTriggerConfig:
        """Return the webhook trigger configuration for the workflow."""
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            return self._trigger_layer.get_webhook_config(workflow_id)

    async def handle_webhook_trigger(
        self,
        workflow_id: UUID,
        *,
        method: str,
        headers: Mapping[str, str],
        query_params: Mapping[str, str],
        payload: Any,
        source_ip: str | None,
    ) -> WorkflowRun:
        """Validate input and enqueue a run for the webhook event."""
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            version = await self._get_latest_version_locked(workflow_id)
            await self._ensure_workflow_health(workflow_id, actor="webhook")
            request = WebhookRequest(
                method=method,
                headers=headers,
                query_params=query_params,
                payload=payload,
                source_ip=source_ip,
            )
            dispatch = self._trigger_layer.prepare_webhook_dispatch(
                workflow_id, request
            )
            run = await self._create_run_locked(
                workflow_id=workflow_id,
                workflow_version_id=version.id,
                triggered_by=dispatch.triggered_by,
                input_payload=dispatch.input_payload,
                actor=dispatch.actor,
            )
            return run.model_copy(deep=True)

    async def configure_cron_trigger(
        self, workflow_id: UUID, config: CronTriggerConfig
    ) -> CronTriggerConfig:
        """Persist cron trigger configuration for the workflow."""
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            normalized = self._trigger_layer.configure_cron(workflow_id, config)
            async with self._connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO cron_triggers (workflow_id, config)
                    VALUES (?, ?)
                    ON CONFLICT(workflow_id) DO UPDATE SET config=excluded.config
                    """,
                    (str(workflow_id), self._dump_config(normalized)),
                )
            return normalized.model_copy(deep=True)

    async def get_cron_trigger_config(self, workflow_id: UUID) -> CronTriggerConfig:
        """Return the cron trigger configuration for the workflow."""
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            return self._trigger_layer.get_cron_config(workflow_id)

    async def dispatch_due_cron_runs(
        self, *, now: datetime | None = None
    ) -> list[WorkflowRun]:
        """Dispatch runs for cron triggers that are ready."""
        await self._ensure_initialized()
        reference = now or datetime.now(tz=UTC)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)

        runs: list[WorkflowRun] = []

        async with self._lock:
            plans = self._trigger_layer.collect_due_cron_dispatches(now=reference)
            for plan in plans:
                try:
                    version = await self._get_latest_version_locked(plan.workflow_id)
                except WorkflowVersionNotFoundError:
                    continue

                await self._ensure_workflow_health(plan.workflow_id, actor="cron")

                run = await self._create_run_locked(
                    workflow_id=plan.workflow_id,
                    workflow_version_id=version.id,
                    triggered_by="cron",
                    input_payload={
                        "scheduled_for": plan.scheduled_for.isoformat(),
                        "timezone": plan.timezone,
                    },
                    actor="cron",
                )
                self._trigger_layer.commit_cron_dispatch(plan.workflow_id)
                runs.append(run.model_copy(deep=True))
            return runs

    async def dispatch_manual_runs(
        self, request: ManualDispatchRequest
    ) -> list[WorkflowRun]:
        """Dispatch manual workflow runs according to the request payload."""
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(request.workflow_id)
            try:
                latest_version = await self._get_latest_version_locked(
                    request.workflow_id
                )
            except WorkflowVersionNotFoundError as exc:
                raise WorkflowVersionNotFoundError(str(request.workflow_id)) from exc
            default_version_id = latest_version.id
            plan = self._trigger_layer.prepare_manual_dispatch(
                request, default_workflow_version_id=default_version_id
            )

            await self._ensure_workflow_health(
                request.workflow_id, actor=plan.actor or plan.triggered_by
            )

            runs: list[WorkflowRun] = []
            for resolved in plan.runs:
                version = await self._get_version_locked(resolved.workflow_version_id)
                if version.workflow_id != request.workflow_id:
                    raise WorkflowVersionNotFoundError(
                        str(resolved.workflow_version_id)
                    )

            for resolved in plan.runs:
                run = await self._create_run_locked(
                    workflow_id=request.workflow_id,
                    workflow_version_id=resolved.workflow_version_id,
                    triggered_by=plan.triggered_by,
                    input_payload=resolved.input_payload,
                    actor=plan.actor,
                )
                runs.append(run.model_copy(deep=True))
            return runs

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

    async def configure_retry_policy(
        self, workflow_id: UUID, config: RetryPolicyConfig
    ) -> RetryPolicyConfig:
        """Persist retry policy configuration for the workflow."""
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            normalized = self._trigger_layer.configure_retry_policy(workflow_id, config)
            async with self._connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO retry_policies (workflow_id, config)
                    VALUES (?, ?)
                    ON CONFLICT(workflow_id) DO UPDATE SET config=excluded.config
                    """,
                    (str(workflow_id), self._dump_config(normalized)),
                )
            return normalized.model_copy(deep=True)

    async def get_retry_policy_config(self, workflow_id: UUID) -> RetryPolicyConfig:
        """Return the retry policy configuration for the workflow."""
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            return self._trigger_layer.get_retry_policy_config(workflow_id)

    async def schedule_retry_for_run(
        self, run_id: UUID, *, failed_at: datetime | None = None
    ) -> RetryDecision | None:
        """Return the next retry decision for the specified run if available."""
        await self._ensure_initialized()
        async with self._lock:
            await self._get_run_locked(run_id)
            return self._trigger_layer.next_retry_for_run(run_id, failed_at=failed_at)

    async def _update_run(
        self, run_id: UUID, updater: Callable[[WorkflowRun], None]
    ) -> WorkflowRun:
        await self._ensure_initialized()
        async with self._lock:
            run = await self._get_run_locked(run_id)
            updater(run)
            async with self._connection() as conn:
                await conn.execute(
                    """
                    UPDATE workflow_runs
                       SET status = ?, payload = ?, updated_at = ?
                     WHERE id = ?
                    """,
                    (
                        run.status.value,
                        self._dump_model(run),
                        run.updated_at.isoformat(),
                        str(run.id),
                    ),
                )
            return run.model_copy(deep=True)

    def _release_cron_run(self, run_id: UUID) -> None:
        self._trigger_layer.release_cron_run(run_id)

    async def _get_workflow_locked(self, workflow_id: UUID) -> Workflow:
        async with self._connection() as conn:
            cursor = await conn.execute(
                "SELECT payload FROM workflows WHERE id = ?", (str(workflow_id),)
            )
            row = await cursor.fetchone()
        if row is None:
            raise WorkflowNotFoundError(str(workflow_id))
        return Workflow.model_validate_json(row["payload"])

    async def _get_version_locked(self, version_id: UUID) -> WorkflowVersion:
        async with self._connection() as conn:
            cursor = await conn.execute(
                "SELECT payload FROM workflow_versions WHERE id = ?",
                (str(version_id),),
            )
            row = await cursor.fetchone()
        if row is None:
            raise WorkflowVersionNotFoundError(str(version_id))
        return WorkflowVersion.model_validate_json(row["payload"])

    async def _get_latest_version_locked(self, workflow_id: UUID) -> WorkflowVersion:
        async with self._connection() as conn:
            cursor = await conn.execute(
                """
                SELECT payload
                  FROM workflow_versions
                 WHERE workflow_id = ?
              ORDER BY version DESC
                 LIMIT 1
                """,
                (str(workflow_id),),
            )
            row = await cursor.fetchone()
        if row is None:
            raise WorkflowVersionNotFoundError("latest")
        return WorkflowVersion.model_validate_json(row["payload"])

    async def _get_run_locked(self, run_id: UUID) -> WorkflowRun:
        async with self._connection() as conn:
            cursor = await conn.execute(
                (
                    "SELECT payload, workflow_id, triggered_by, status "
                    "FROM workflow_runs WHERE id = ?"
                ),
                (str(run_id),),
            )
            row = await cursor.fetchone()
        if row is None:
            raise WorkflowRunNotFoundError(str(run_id))
        return WorkflowRun.model_validate_json(row["payload"])

    async def _create_run_locked(
        self,
        *,
        workflow_id: UUID,
        workflow_version_id: UUID,
        triggered_by: str,
        input_payload: Mapping[str, Any],
        actor: str | None,
    ) -> WorkflowRun:
        version = await self._get_version_locked(workflow_version_id)
        if version.workflow_id != workflow_id:
            raise WorkflowVersionNotFoundError(str(workflow_version_id))

        run = WorkflowRun(
            workflow_version_id=workflow_version_id,
            triggered_by=triggered_by,
            input_payload=dict(input_payload),
        )
        run.record_event(actor=actor or triggered_by, action="run_created")

        async with self._connection() as conn:
            await conn.execute(
                """
                INSERT INTO workflow_runs (
                    id,
                    workflow_id,
                    workflow_version_id,
                    status,
                    triggered_by,
                    payload,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(run.id),
                    str(workflow_id),
                    str(workflow_version_id),
                    run.status.value,
                    run.triggered_by,
                    self._dump_model(run),
                    run.created_at.isoformat(),
                    run.updated_at.isoformat(),
                ),
            )

        self._trigger_layer.track_run(workflow_id, run.id)
        if triggered_by == "cron":
            self._trigger_layer.register_cron_run(run.id)
        return run

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
                        config TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS retry_policies (
                        workflow_id TEXT PRIMARY KEY,
                        config TEXT NOT NULL
                    );
                    """
                )

            await self._hydrate_trigger_state()
            self._initialized = True

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

            cursor = await conn.execute("SELECT workflow_id, config FROM cron_triggers")
            for row in await cursor.fetchall():
                workflow_id = UUID(row["workflow_id"])
                cron_config = CronTriggerConfig.model_validate_json(row["config"])
                self._trigger_layer.configure_cron(workflow_id, cron_config)

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

    @staticmethod
    def _dump_model(model: Workflow | WorkflowVersion | WorkflowRun) -> str:
        return json.dumps(model.model_dump(mode="json"))

    @staticmethod
    def _dump_config(
        config: WebhookTriggerConfig | CronTriggerConfig | RetryPolicyConfig,
    ) -> str:
        return json.dumps(config.model_dump(mode="json"))


__all__ = ["SqliteWorkflowRepository"]
