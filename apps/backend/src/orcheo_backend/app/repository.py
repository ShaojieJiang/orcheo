"""In-memory repositories powering the FastAPI service."""

from __future__ import annotations
import asyncio
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import unified_diff
from typing import Any
from uuid import UUID
from orcheo.models.workflow import Workflow, WorkflowRun, WorkflowVersion
from orcheo.triggers.cron import CronTriggerConfig
from orcheo.triggers.layer import TriggerLayer
from orcheo.triggers.manual import ManualDispatchRequest
from orcheo.triggers.retry import RetryDecision, RetryPolicyConfig
from orcheo.triggers.webhook import WebhookRequest, WebhookTriggerConfig


class RepositoryError(RuntimeError):
    """Base class for repository specific errors."""


class WorkflowNotFoundError(RepositoryError):
    """Raised when a workflow cannot be located."""


class WorkflowVersionNotFoundError(RepositoryError):
    """Raised when attempting to access an unknown workflow version."""


class WorkflowRunNotFoundError(RepositoryError):
    """Raised when attempting to access an unknown workflow run."""


@dataclass(slots=True)
class VersionDiff:
    """Represents a unified diff between two workflow graphs."""

    base_version: int
    target_version: int
    diff: list[str]


class InMemoryWorkflowRepository:
    """Simple async-safe in-memory repository for workflows and runs."""

    def __init__(self) -> None:
        """Initialize the storage containers used by the repository."""
        self._lock = asyncio.Lock()
        self._workflows: dict[UUID, Workflow] = {}
        self._workflow_versions: dict[UUID, list[UUID]] = {}
        self._versions: dict[UUID, WorkflowVersion] = {}
        self._runs: dict[UUID, WorkflowRun] = {}
        self._version_runs: dict[UUID, list[UUID]] = {}
        self._trigger_layer = TriggerLayer()

    async def list_workflows(self) -> list[Workflow]:
        """Return all workflows stored within the repository."""
        async with self._lock:
            return [
                workflow.model_copy(deep=True) for workflow in self._workflows.values()
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
        """Persist a new workflow and return the created instance."""
        async with self._lock:
            workflow = Workflow(
                name=name,
                slug=slug or "",
                description=description,
                tags=list(tags or []),
            )
            workflow.record_event(actor=actor, action="workflow_created")
            self._workflows[workflow.id] = workflow
            self._workflow_versions.setdefault(workflow.id, [])
            return workflow.model_copy(deep=True)

    async def get_workflow(self, workflow_id: UUID) -> Workflow:
        """Retrieve a workflow by its identifier."""
        async with self._lock:
            workflow = self._workflows.get(workflow_id)
            if workflow is None:
                raise WorkflowNotFoundError(str(workflow_id))
            return workflow.model_copy(deep=True)

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
        """Update workflow metadata and record an audit event."""
        async with self._lock:
            workflow = self._workflows.get(workflow_id)
            if workflow is None:
                raise WorkflowNotFoundError(str(workflow_id))

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
            return workflow.model_copy(deep=True)

    async def archive_workflow(self, workflow_id: UUID, *, actor: str) -> Workflow:
        """Archive a workflow by delegating to the update helper."""
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
        """Create and store a new workflow version."""
        async with self._lock:
            workflow = self._workflows.get(workflow_id)
            if workflow is None:
                raise WorkflowNotFoundError(str(workflow_id))

            version_ids = self._workflow_versions.setdefault(workflow_id, [])
            next_version_number = len(version_ids) + 1
            version = WorkflowVersion(
                workflow_id=workflow_id,
                version=next_version_number,
                graph=json.loads(json.dumps(graph)),
                metadata=dict(metadata),
                created_by=created_by,
                notes=notes,
            )
            version.record_event(actor=created_by, action="version_created")
            self._versions[version.id] = version
            version_ids.append(version.id)
            self._version_runs.setdefault(version.id, [])
            return version.model_copy(deep=True)

    async def list_versions(self, workflow_id: UUID) -> list[WorkflowVersion]:
        """Return the versions belonging to the given workflow."""
        async with self._lock:
            version_ids = self._workflow_versions.get(workflow_id)
            if version_ids is None:
                raise WorkflowNotFoundError(str(workflow_id))
            return [
                self._versions[version_id].model_copy(deep=True)
                for version_id in version_ids
            ]

    async def get_version_by_number(
        self, workflow_id: UUID, version_number: int
    ) -> WorkflowVersion:
        """Fetch a workflow version by its human readable number."""
        async with self._lock:
            version_ids = self._workflow_versions.get(workflow_id)
            if version_ids is None:
                raise WorkflowNotFoundError(str(workflow_id))
            for version_id in version_ids:
                version = self._versions[version_id]
                if version.version == version_number:
                    return version.model_copy(deep=True)
            raise WorkflowVersionNotFoundError(f"v{version_number}")

    async def get_version(self, version_id: UUID) -> WorkflowVersion:
        """Retrieve a workflow version by its identifier."""
        async with self._lock:
            version = self._versions.get(version_id)
            if version is None:
                raise WorkflowVersionNotFoundError(str(version_id))
            return version.model_copy(deep=True)

    async def get_latest_version(self, workflow_id: UUID) -> WorkflowVersion:
        """Return the most recent workflow version for the workflow."""
        async with self._lock:
            version_ids = self._workflow_versions.get(workflow_id)
            if version_ids is None:
                raise WorkflowNotFoundError(str(workflow_id))
            if not version_ids:
                raise WorkflowVersionNotFoundError("latest")
            latest_version_id = version_ids[-1]
            version = self._versions.get(latest_version_id)
            if version is None:
                raise WorkflowVersionNotFoundError(str(latest_version_id))
            return version.model_copy(deep=True)

    async def diff_versions(
        self, workflow_id: UUID, base_version: int, target_version: int
    ) -> VersionDiff:
        """Compute a unified diff between two workflow versions."""
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
        """Create a workflow run tied to a version."""
        async with self._lock:
            if workflow_id not in self._workflows:
                raise WorkflowNotFoundError(str(workflow_id))

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

    def _create_run_locked(
        self,
        *,
        workflow_id: UUID,
        workflow_version_id: UUID,
        triggered_by: str,
        input_payload: Mapping[str, Any],
        actor: str | None = None,
    ) -> WorkflowRun:
        """Create and store a workflow run. Caller must hold the lock."""
        if workflow_id not in self._workflows:  # pragma: no cover, defensive
            raise WorkflowNotFoundError(str(workflow_id))

        version = self._versions.get(workflow_version_id)
        if version is None or version.workflow_id != workflow_id:
            raise WorkflowVersionNotFoundError(str(workflow_version_id))

        run = WorkflowRun(
            workflow_version_id=workflow_version_id,
            triggered_by=triggered_by,
            input_payload=dict(input_payload),
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

    async def reset(self) -> None:
        """Clear all stored workflows, versions, and runs."""
        async with self._lock:
            self._workflows.clear()
            self._workflow_versions.clear()
            self._versions.clear()
            self._runs.clear()
            self._version_runs.clear()
            self._trigger_layer.reset()

    def _release_cron_run(self, run_id: UUID) -> None:
        """Release overlap tracking for the provided cron run."""
        self._trigger_layer.release_cron_run(run_id)

    async def configure_webhook_trigger(
        self, workflow_id: UUID, config: WebhookTriggerConfig
    ) -> WebhookTriggerConfig:
        """Persist webhook trigger configuration for a workflow."""
        async with self._lock:
            if workflow_id not in self._workflows:
                raise WorkflowNotFoundError(str(workflow_id))
            return self._trigger_layer.configure_webhook(workflow_id, config)

    async def get_webhook_trigger_config(
        self, workflow_id: UUID
    ) -> WebhookTriggerConfig:
        """Return the webhook configuration for the workflow."""
        async with self._lock:
            if workflow_id not in self._workflows:
                raise WorkflowNotFoundError(str(workflow_id))
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
        """Validate webhook input and enqueue a workflow run."""
        async with self._lock:
            workflow = self._workflows.get(workflow_id)
            if workflow is None:
                raise WorkflowNotFoundError(str(workflow_id))

            version_ids = self._workflow_versions.get(workflow_id)
            if not version_ids:
                raise WorkflowVersionNotFoundError("latest")
            latest_version_id = version_ids[-1]
            version = self._versions.get(latest_version_id)
            if version is None:
                raise WorkflowVersionNotFoundError(str(latest_version_id))

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
            run = self._create_run_locked(
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
        """Persist cron trigger configuration for a workflow."""
        async with self._lock:
            if workflow_id not in self._workflows:
                raise WorkflowNotFoundError(str(workflow_id))
            return self._trigger_layer.configure_cron(workflow_id, config)

    async def get_cron_trigger_config(self, workflow_id: UUID) -> CronTriggerConfig:
        """Return the configured cron trigger definition."""
        async with self._lock:
            if workflow_id not in self._workflows:
                raise WorkflowNotFoundError(str(workflow_id))
            return self._trigger_layer.get_cron_config(workflow_id)

    async def dispatch_due_cron_runs(
        self, *, now: datetime | None = None
    ) -> list[WorkflowRun]:
        """Evaluate cron schedules and enqueue runs that are due."""
        reference = now or datetime.now(tz=UTC)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)

        async with self._lock:
            runs: list[WorkflowRun] = []
            plans = self._trigger_layer.collect_due_cron_dispatches(now=reference)
            for plan in plans:
                workflow_id = plan.workflow_id
                if workflow_id not in self._workflows:
                    continue
                version_ids = self._workflow_versions.get(workflow_id)
                if not version_ids:
                    continue
                latest_version_id = version_ids[-1]
                version = self._versions.get(latest_version_id)
                if version is None:
                    continue

                run = self._create_run_locked(
                    workflow_id=workflow_id,
                    workflow_version_id=version.id,
                    triggered_by="cron",
                    input_payload={
                        "scheduled_for": plan.scheduled_for.isoformat(),
                        "timezone": plan.timezone,
                    },
                    actor="cron",
                )
                self._trigger_layer.commit_cron_dispatch(workflow_id)
                runs.append(run.model_copy(deep=True))
            return runs

    async def dispatch_manual_runs(
        self, request: ManualDispatchRequest
    ) -> list[WorkflowRun]:
        """Dispatch one or more manual runs for a workflow."""
        async with self._lock:
            if request.workflow_id not in self._workflows:
                raise WorkflowNotFoundError(str(request.workflow_id))

            version_ids = self._workflow_versions.get(request.workflow_id)
            if not version_ids:
                raise WorkflowVersionNotFoundError(str(request.workflow_id))

            default_version_id = version_ids[-1]
            runs: list[WorkflowRun] = []
            plan = self._trigger_layer.prepare_manual_dispatch(
                request, default_workflow_version_id=default_version_id
            )
            triggered_by = plan.triggered_by
            resolved_runs = plan.runs

            for resolved in resolved_runs:
                version = self._versions.get(resolved.workflow_version_id)
                if version is None or version.workflow_id != request.workflow_id:
                    raise WorkflowVersionNotFoundError(  # pragma: no cover, defensive
                        str(resolved.workflow_version_id)
                    )

            for resolved in resolved_runs:
                run = self._create_run_locked(
                    workflow_id=request.workflow_id,
                    workflow_version_id=resolved.workflow_version_id,
                    triggered_by=triggered_by,
                    input_payload=resolved.input_payload,
                    actor=plan.actor,
                )
                runs.append(run.model_copy(deep=True))
            return runs

    async def configure_retry_policy(
        self, workflow_id: UUID, config: RetryPolicyConfig
    ) -> RetryPolicyConfig:
        """Persist retry policy configuration for the workflow."""
        async with self._lock:
            if workflow_id not in self._workflows:
                raise WorkflowNotFoundError(str(workflow_id))
            return self._trigger_layer.configure_retry_policy(workflow_id, config)

    async def get_retry_policy_config(self, workflow_id: UUID) -> RetryPolicyConfig:
        """Return the retry policy configuration for the workflow."""
        async with self._lock:
            if workflow_id not in self._workflows:
                raise WorkflowNotFoundError(str(workflow_id))
            return self._trigger_layer.get_retry_policy_config(workflow_id)

    async def schedule_retry_for_run(
        self, run_id: UUID, *, failed_at: datetime | None = None
    ) -> RetryDecision | None:
        """Return the next retry decision for the specified run."""
        async with self._lock:
            if run_id not in self._runs:
                raise WorkflowRunNotFoundError(str(run_id))
            return self._trigger_layer.next_retry_for_run(run_id, failed_at=failed_at)


__all__ = [
    "InMemoryWorkflowRepository",
    "RepositoryError",
    "VersionDiff",
    "WorkflowNotFoundError",
    "WorkflowRunNotFoundError",
    "WorkflowVersionNotFoundError",
]
