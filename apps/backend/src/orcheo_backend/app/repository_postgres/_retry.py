"""Retry policy persistence helpers."""

from __future__ import annotations
from datetime import datetime
from uuid import UUID
from orcheo.triggers.retry import RetryDecision, RetryPolicyConfig
from orcheo_backend.app.repository_postgres._persistence import PostgresPersistenceMixin


class RetryPolicyMixin(PostgresPersistenceMixin):
    """Configure and query retry policies."""

    async def configure_retry_policy(
        self,
        workflow_id: UUID,
        config: RetryPolicyConfig,
    ) -> RetryPolicyConfig:
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            normalized = self._trigger_layer.configure_retry_policy(workflow_id, config)
            async with self._connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO retry_policies (workflow_id, config)
                    VALUES (%s, %s)
                    ON CONFLICT(workflow_id) DO UPDATE SET config=EXCLUDED.config
                    """,
                    (str(workflow_id), self._dump_config(normalized)),
                )
            return normalized.model_copy(deep=True)

    async def get_retry_policy_config(self, workflow_id: UUID) -> RetryPolicyConfig:
        await self._ensure_initialized()
        async with self._lock:
            await self._get_workflow_locked(workflow_id)
            return self._trigger_layer.get_retry_policy_config(workflow_id)

    async def schedule_retry_for_run(
        self,
        run_id: UUID,
        *,
        failed_at: datetime | None = None,
    ) -> RetryDecision | None:
        await self._ensure_initialized()
        async with self._lock:
            await self._get_run_locked(run_id)
            return self._trigger_layer.next_retry_for_run(run_id, failed_at=failed_at)


__all__ = ["RetryPolicyMixin"]
