"""Shared state and helpers for the in-memory repository."""

from __future__ import annotations
import asyncio
from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID
from orcheo.models.workflow import Workflow, WorkflowRun, WorkflowVersion
from orcheo.triggers.layer import TriggerLayer
from orcheo.vault.oauth import CredentialHealthError, OAuthCredentialService
from orcheo_backend.app.repository.errors import (
    WorkflowNotFoundError,
    WorkflowRunNotFoundError,
    WorkflowVersionNotFoundError,
)


class InMemoryRepositoryState:
    """Holds shared state and primitives for the in-memory repository."""

    def __init__(
        self, credential_service: OAuthCredentialService | None = None
    ) -> None:
        """Initialize the repository state containers and dependencies."""
        self._lock = asyncio.Lock()
        self._workflows: dict[UUID, Workflow] = {}
        self._workflow_versions: dict[UUID, list[UUID]] = {}
        self._versions: dict[UUID, WorkflowVersion] = {}
        self._runs: dict[UUID, WorkflowRun] = {}
        self._version_runs: dict[UUID, list[UUID]] = {}
        self._credential_service = credential_service
        self._trigger_layer = TriggerLayer(health_guard=credential_service)

    async def reset(self) -> None:
        """Clear all stored workflows, versions, and runs."""
        async with self._lock:
            self._workflows.clear()
            self._workflow_versions.clear()
            self._versions.clear()
            self._runs.clear()
            self._version_runs.clear()
            self._trigger_layer.reset()

    def _create_run_locked(
        self,
        *,
        workflow_id: UUID,
        workflow_version_id: UUID,
        triggered_by: str,
        input_payload: Mapping[str, Any],
        actor: str | None = None,
        runnable_config: Mapping[str, Any] | None = None,
    ) -> WorkflowRun:
        """Create and store a workflow run. Caller must hold the lock."""
        if workflow_id not in self._workflows:  # pragma: no cover, defensive
            raise WorkflowNotFoundError(str(workflow_id))

        version = self._versions.get(workflow_version_id)
        if version is None or version.workflow_id != workflow_id:
            raise WorkflowVersionNotFoundError(str(workflow_version_id))

        config_payload: dict[str, Any] = {}
        if runnable_config:
            if hasattr(runnable_config, "model_dump"):
                config_payload = runnable_config.model_dump(mode="json")  # type: ignore[arg-type]
            elif isinstance(runnable_config, Mapping):  # pragma: no branch
                config_payload = dict(runnable_config)
        tags = (
            list(config_payload.get("tags", []))
            if isinstance(config_payload, dict)
            else []
        )
        callbacks = (
            list(config_payload.get("callbacks", []))
            if isinstance(config_payload, dict)
            else []
        )
        metadata = (
            dict(config_payload.get("metadata", {}))
            if isinstance(config_payload, Mapping)
            else {}
        )
        run_name = (
            config_payload.get("run_name")
            if isinstance(config_payload, Mapping)
            else None
        )
        run = WorkflowRun(
            workflow_version_id=workflow_version_id,
            triggered_by=triggered_by,
            input_payload=dict(input_payload),
            runnable_config=config_payload if isinstance(config_payload, dict) else {},
            tags=tags,
            callbacks=callbacks,
            metadata=metadata,
            run_name=run_name,
        )
        run.record_event(actor=actor or triggered_by, action="run_created")
        self._runs[run.id] = run
        self._version_runs.setdefault(workflow_version_id, []).append(run.id)
        self._trigger_layer.track_run(workflow_id, run.id)
        if triggered_by == "cron":
            self._trigger_layer.register_cron_run(run.id)
        return run

    async def _update_run(
        self, run_id: UUID, updater: Callable[[WorkflowRun], None]
    ) -> WorkflowRun:
        """Apply a mutation to a run under lock and return a copy."""
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise WorkflowRunNotFoundError(str(run_id))
            updater(run)
            return run.model_copy(deep=True)

    def _release_cron_run(self, run_id: UUID) -> None:
        """Release overlap tracking for the provided cron run."""
        self._trigger_layer.release_cron_run(run_id)

    async def _ensure_workflow_health(
        self, workflow_id: UUID, *, actor: str | None = None
    ) -> None:
        service = self._credential_service
        if service is None:
            return
        report = await service.ensure_workflow_health(workflow_id, actor=actor)
        if not report.is_healthy:
            raise CredentialHealthError(report)


__all__ = ["InMemoryRepositoryState"]
