"""Retry policy helpers for the in-memory repository."""

from __future__ import annotations
from datetime import datetime
from uuid import UUID
from orcheo.triggers.retry import RetryDecision, RetryPolicyConfig
from orcheo_backend.app.repository.errors import (
    WorkflowNotFoundError,
    WorkflowRunNotFoundError,
)
from orcheo_backend.app.repository.in_memory.state import InMemoryRepositoryState


class RetryPolicyMixin(InMemoryRepositoryState):
    """Supports retry configuration and scheduling."""

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


__all__ = ["RetryPolicyMixin"]
