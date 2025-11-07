"""Workflow run lifecycle helpers."""

from __future__ import annotations
from typing import Any
from uuid import UUID
from orcheo.models.workflow import WorkflowRun
from orcheo_backend.app.repository.errors import (
    WorkflowNotFoundError,
    WorkflowRunNotFoundError,
)
from orcheo_backend.app.repository.in_memory.state import InMemoryRepositoryState


class WorkflowRunMixin(InMemoryRepositoryState):
    """Implements run creation and state transitions."""

    async def create_run(
        self,
        workflow_id: UUID,
        *,
        workflow_version_id: UUID,
        triggered_by: str,
        input_payload: dict[str, Any],
        actor: str | None = None,
    ) -> WorkflowRun:
        """Create a workflow run tied to a version."""
        async with self._lock:
            if workflow_id not in self._workflows:
                raise WorkflowNotFoundError(str(workflow_id))

            await self._ensure_workflow_health(workflow_id, actor=actor or triggered_by)

            run = self._create_run_locked(
                workflow_id=workflow_id,
                workflow_version_id=workflow_version_id,
                triggered_by=triggered_by,
                input_payload=input_payload,
                actor=actor,
            )
            return run.model_copy(deep=True)

    async def list_runs_for_workflow(self, workflow_id: UUID) -> list[WorkflowRun]:
        """Return all runs associated with the provided workflow."""
        async with self._lock:
            if workflow_id not in self._workflows:
                raise WorkflowNotFoundError(str(workflow_id))
            version_ids = self._workflow_versions.get(workflow_id, [])
            run_ids = [
                run_id
                for version_id in version_ids
                for run_id in self._version_runs.get(version_id, [])
            ]
            return [self._runs[run_id].model_copy(deep=True) for run_id in run_ids]

    async def get_run(self, run_id: UUID) -> WorkflowRun:
        """Fetch a run by its identifier."""
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise WorkflowRunNotFoundError(str(run_id))
            return run.model_copy(deep=True)

    async def mark_run_started(self, run_id: UUID, *, actor: str) -> WorkflowRun:
        """Mark the specified run as started."""
        return await self._update_run(run_id, lambda run: run.mark_started(actor=actor))

    async def mark_run_succeeded(
        self,
        run_id: UUID,
        *,
        actor: str,
        output: dict[str, Any] | None,
    ) -> WorkflowRun:
        """Mark the specified run as succeeded with optional output."""
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
        """Transition the run to a failed state."""
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
        """Cancel a run, optionally including a reason."""
        run = await self._update_run(
            run_id,
            lambda run: run.mark_cancelled(actor=actor, reason=reason),
        )
        self._release_cron_run(run_id)
        self._trigger_layer.clear_retry_state(run_id)
        return run


__all__ = ["WorkflowRunMixin"]
