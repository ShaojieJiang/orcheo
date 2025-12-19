"""Low-level SQLite persistence helpers."""

from __future__ import annotations
import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID
from orcheo.models.workflow import Workflow, WorkflowRun, WorkflowVersion
from orcheo_backend.app.repository import (
    WorkflowNotFoundError,
    WorkflowRunNotFoundError,
    WorkflowVersionNotFoundError,
)
from orcheo_backend.app.repository_sqlite._base import SqliteRepositoryBase


class SqlitePersistenceMixin(SqliteRepositoryBase):
    """Expose locked fetch helpers shared across mixins."""

    @staticmethod
    def _deserialize_workflow(payload_json: str) -> Workflow:
        """Return a Workflow instance while stripping deprecated fields."""
        payload = json.loads(payload_json)
        payload.pop("publish_token_hash", None)
        payload.pop("publish_token_rotated_at", None)
        return Workflow.model_validate(payload)

    async def _get_workflow_locked(self, workflow_id: UUID) -> Workflow:
        async with self._connection() as conn:
            cursor = await conn.execute(
                "SELECT payload FROM workflows WHERE id = ?", (str(workflow_id),)
            )
            row = await cursor.fetchone()
        if row is None:
            raise WorkflowNotFoundError(str(workflow_id))
        return self._deserialize_workflow(row["payload"])

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
        runnable_config: Mapping[str, Any] | None = None,
    ) -> WorkflowRun:
        version = await self._get_version_locked(workflow_version_id)
        if version.workflow_id != workflow_id:
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


__all__ = ["SqlitePersistenceMixin"]
