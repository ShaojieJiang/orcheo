"""In-memory repositories powering the FastAPI service."""

from __future__ import annotations
import asyncio
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from difflib import unified_diff
from typing import Any
from uuid import UUID
from orcheo.models.workflow import Workflow, WorkflowRun, WorkflowVersion


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
    ) -> WorkflowRun:
        """Create a workflow run tied to a version."""
        async with self._lock:
            if workflow_id not in self._workflows:
                raise WorkflowNotFoundError(str(workflow_id))

            version = self._versions.get(workflow_version_id)
            if version is None:
                raise WorkflowVersionNotFoundError(str(workflow_version_id))
            if version.workflow_id != workflow_id:
                raise WorkflowVersionNotFoundError(str(workflow_version_id))

            run = WorkflowRun(
                workflow_version_id=workflow_version_id,
                triggered_by=triggered_by,
                input_payload=dict(input_payload),
            )
            run.record_event(actor=triggered_by, action="run_created")
            self._runs[run.id] = run
            self._version_runs.setdefault(workflow_version_id, []).append(run.id)
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
        return await self._update_run(
            run_id,
            lambda run: run.mark_succeeded(actor=actor, output=output),
        )

    async def mark_run_failed(
        self,
        run_id: UUID,
        *,
        actor: str,
        error: str,
    ) -> WorkflowRun:
        """Transition the run to a failed state."""
        return await self._update_run(
            run_id,
            lambda run: run.mark_failed(actor=actor, error=error),
        )

    async def mark_run_cancelled(
        self,
        run_id: UUID,
        *,
        actor: str,
        reason: str | None,
    ) -> WorkflowRun:
        """Cancel a run, optionally including a reason."""
        return await self._update_run(
            run_id,
            lambda run: run.mark_cancelled(actor=actor, reason=reason),
        )

    async def reset(self) -> None:
        """Clear all stored workflows, versions, and runs."""
        async with self._lock:
            self._workflows.clear()
            self._workflow_versions.clear()
            self._versions.clear()
            self._runs.clear()
            self._version_runs.clear()


__all__ = [
    "InMemoryWorkflowRepository",
    "RepositoryError",
    "VersionDiff",
    "WorkflowNotFoundError",
    "WorkflowRunNotFoundError",
    "WorkflowVersionNotFoundError",
]
