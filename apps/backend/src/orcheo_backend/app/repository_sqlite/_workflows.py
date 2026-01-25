"""Workflow CRUD operations for the SQLite repository."""

from __future__ import annotations
from collections.abc import Iterable
from typing import Any
from uuid import UUID
from orcheo.models.workflow import Workflow
from orcheo_backend.app.repository.errors import (
    WorkflowNotFoundError,
    WorkflowPublishStateError,
)
from orcheo_backend.app.repository_sqlite._persistence import SqlitePersistenceMixin


class WorkflowRepositoryMixin(SqlitePersistenceMixin):
    """Helpers for managing workflow metadata."""

    async def list_workflows(self, *, include_archived: bool = False) -> list[Workflow]:
        await self._ensure_initialized()
        async with self._lock:
            async with self._connection() as conn:
                cursor = await conn.execute(
                    "SELECT payload FROM workflows ORDER BY created_at ASC"
                )
                rows = await cursor.fetchall()
            workflows = [
                self._deserialize_workflow(row["payload"]).model_copy(deep=True)
                for row in rows
            ]
            if include_archived:
                return workflows
            return [wf for wf in workflows if not wf.is_archived]

    async def create_workflow(
        self,
        *,
        name: str,
        slug: str | None,
        description: str | None,
        tags: Iterable[str] | None,
        actor: str,
    ) -> Workflow:
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
                    metadata["tags"] = {
                        "from": workflow.tags,
                        "to": normalized_tags,
                    }
                    workflow.tags = normalized_tags

            if is_archived is not None and is_archived != workflow.is_archived:
                if is_archived and workflow.is_public:
                    workflow.revoke_publish(actor=actor)
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
        require_login: bool,
        actor: str,
    ) -> Workflow:
        await self._ensure_initialized()
        async with self._lock:
            workflow = await self._get_workflow_locked(workflow_id)
            if workflow.is_archived:
                raise WorkflowNotFoundError(str(workflow_id))
            try:
                workflow.publish(
                    require_login=require_login,
                    actor=actor,
                )
            except ValueError as exc:
                raise WorkflowPublishStateError(str(exc)) from exc
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

    async def revoke_publish(self, workflow_id: UUID, *, actor: str) -> Workflow:
        await self._ensure_initialized()
        async with self._lock:
            workflow = await self._get_workflow_locked(workflow_id)
            if workflow.is_archived:
                raise WorkflowNotFoundError(str(workflow_id))
            try:
                workflow.revoke_publish(actor=actor)
            except ValueError as exc:
                raise WorkflowPublishStateError(str(exc)) from exc
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


__all__ = ["WorkflowRepositoryMixin"]
