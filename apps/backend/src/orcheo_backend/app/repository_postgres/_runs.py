"""Workflow run persistence and lifecycle helpers."""

from __future__ import annotations
from collections.abc import Callable
from typing import Any
from uuid import UUID
from orcheo.models.workflow import WorkflowRun
from orcheo_backend.app.repository_postgres._persistence import PostgresPersistenceMixin


class WorkflowRunMixin(PostgresPersistenceMixin):
    """Create and update workflow runs."""

    async def create_run(
        self,
        workflow_id: UUID,
        *,
        workflow_version_id: UUID,
        triggered_by: str,
        input_payload: dict[str, Any],
        actor: str | None = None,
        runnable_config: dict[str, Any] | None = None,
    ) -> WorkflowRun:
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
                runnable_config=runnable_config,
            )
            return run.model_copy(deep=True)

    async def list_runs_for_workflow(self, workflow_id: UUID) -> list[WorkflowRun]:
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            async with self._connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT payload
                      FROM workflow_runs
                     WHERE workflow_id = %s
                  ORDER BY created_at ASC
                    """,
                    (str(workflow_id),),
                )
                rows = await cursor.fetchall()
            result = []
            for row in rows:
                payload = row["payload"]
                if isinstance(payload, str):
                    run = WorkflowRun.model_validate_json(payload)
                else:
                    run = WorkflowRun.model_validate(payload)
                result.append(run.model_copy(deep=True))
            return result

    async def get_run(self, run_id: UUID) -> WorkflowRun:
        await self._ensure_initialized()
        async with self._lock:
            return await self._get_run_locked(run_id)

    async def mark_run_started(self, run_id: UUID, *, actor: str) -> WorkflowRun:
        return await self._update_run(run_id, lambda run: run.mark_started(actor=actor))

    async def mark_run_succeeded(
        self,
        run_id: UUID,
        *,
        actor: str,
        output: dict[str, Any] | None,
    ) -> WorkflowRun:
        run = await self._update_run(
            run_id,
            lambda candidate: candidate.mark_succeeded(actor=actor, output=output),
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
        run = await self._update_run(
            run_id,
            lambda candidate: candidate.mark_failed(actor=actor, error=error),
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
        run = await self._update_run(
            run_id,
            lambda candidate: candidate.mark_cancelled(actor=actor, reason=reason),
        )
        self._release_cron_run(run_id)
        self._trigger_layer.clear_retry_state(run_id)
        return run

    async def reset(self) -> None:
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                await conn.execute("DELETE FROM workflow_runs")
                await conn.execute("DELETE FROM workflow_versions")
                await conn.execute("DELETE FROM workflows")
                await conn.execute("DELETE FROM webhook_triggers")
                await conn.execute("DELETE FROM cron_triggers")
                await conn.execute("DELETE FROM retry_policies")
            self._trigger_layer.reset()

    async def _update_run(
        self,
        run_id: UUID,
        updater: Callable[[WorkflowRun], None],
    ) -> WorkflowRun:
        await self._ensure_initialized()
        async with self._lock:
            run = await self._get_run_locked(run_id)
            updater(run)
            async with self._connection() as conn:
                await conn.execute(
                    """
                    UPDATE workflow_runs
                       SET status = %s, payload = %s, updated_at = %s
                     WHERE id = %s
                    """,
                    (
                        run.status.value,
                        self._dump_model(run),
                        run.updated_at,
                        str(run.id),
                    ),
                )
            return run.model_copy(deep=True)


__all__ = ["WorkflowRunMixin"]
