"""Workflow level operations for the in-memory repository."""

from __future__ import annotations
from collections.abc import Iterable
from typing import Any
from uuid import UUID
from orcheo.models.workflow import Workflow
from orcheo_backend.app.repository.errors import (
    WorkflowNotFoundError,
    WorkflowPublishStateError,
)
from orcheo_backend.app.repository.in_memory.state import InMemoryRepositoryState


class WorkflowCrudMixin(InMemoryRepositoryState):
    """Implements workflow management helpers."""

    async def list_workflows(self, *, include_archived: bool = False) -> list[Workflow]:
        """Return workflows stored within the repository."""
        async with self._lock:
            return [
                workflow.model_copy(deep=True)
                for workflow in self._workflows.values()
                if include_archived or not workflow.is_archived
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
                    metadata["tags"] = {
                        "from": workflow.tags,
                        "to": normalized_tags,
                    }
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

    async def publish_workflow(
        self,
        workflow_id: UUID,
        *,
        publish_token_hash: str,
        require_login: bool,
        actor: str,
    ) -> Workflow:
        """Mark the workflow as public with a hashed publish token."""
        async with self._lock:
            workflow = self._workflows.get(workflow_id)
            if workflow is None:
                raise WorkflowNotFoundError(str(workflow_id))
            try:
                workflow.publish(
                    token_hash=publish_token_hash,
                    require_login=require_login,
                    actor=actor,
                )
            except ValueError as exc:
                raise WorkflowPublishStateError(str(exc)) from exc
            return workflow.model_copy(deep=True)

    async def rotate_publish_token(
        self,
        workflow_id: UUID,
        *,
        publish_token_hash: str,
        actor: str,
    ) -> Workflow:
        """Rotate the publish token for the specified workflow."""
        async with self._lock:
            workflow = self._workflows.get(workflow_id)
            if workflow is None:
                raise WorkflowNotFoundError(str(workflow_id))
            try:
                workflow.rotate_publish_token(
                    token_hash=publish_token_hash,
                    actor=actor,
                )
            except ValueError as exc:
                raise WorkflowPublishStateError(str(exc)) from exc
            return workflow.model_copy(deep=True)

    async def revoke_publish(self, workflow_id: UUID, *, actor: str) -> Workflow:
        """Revoke public access for the workflow."""
        async with self._lock:
            workflow = self._workflows.get(workflow_id)
            if workflow is None:
                raise WorkflowNotFoundError(str(workflow_id))
            try:
                workflow.revoke_publish(actor=actor)
            except ValueError as exc:
                raise WorkflowPublishStateError(str(exc)) from exc
            return workflow.model_copy(deep=True)


__all__ = ["WorkflowCrudMixin"]
