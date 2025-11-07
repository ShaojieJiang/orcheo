"""Cleanup helpers for the trigger layer."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from uuid import UUID
from orcheo.triggers.layer.state import TriggerLayerState


class CleanupMixin(TriggerLayerState):
    """Provide shared cleanup utilities for the trigger layer."""

    def _maybe_cleanup_states(self) -> None:
        """Perform state cleanup if needed based on time and size thresholds."""
        now = datetime.now(UTC)
        time_since_cleanup = now - self._last_cleanup

        should_cleanup_by_time = time_since_cleanup >= timedelta(
            hours=self._cleanup_config.cleanup_interval_hours
        )
        should_cleanup_by_size = len(self._retry_states) > (
            self._cleanup_config.max_retry_states
        )

        if should_cleanup_by_time or should_cleanup_by_size:
            self._cleanup_completed_workflows(now)
            self._last_cleanup = now

    def _cleanup_completed_workflows(self, now: datetime) -> None:
        """Remove expired completed workflow state."""
        ttl = timedelta(hours=self._cleanup_config.completed_workflow_ttl_hours)
        expired_workflows = [
            workflow_id
            for workflow_id, completed_at in self._completed_workflows.items()
            if now - completed_at > ttl
        ]

        for workflow_id in expired_workflows:
            self._completed_workflows.pop(workflow_id, None)

        if expired_workflows:
            cleaned_count = len(expired_workflows)
            self._logger.info("Cleaned up %s expired workflow states", cleaned_count)

        if (
            len(self._completed_workflows)
            > self._cleanup_config.max_completed_workflows
        ):
            sorted_workflows = sorted(
                self._completed_workflows.items(),
                key=lambda item: item[1],
            )
            excess_count = (
                len(self._completed_workflows)
                - self._cleanup_config.max_completed_workflows
            )

            for workflow_id, _ in sorted_workflows[:excess_count]:
                self._completed_workflows.pop(workflow_id, None)

            self._logger.info("Cleaned up %s oldest completed workflows", excess_count)

    def get_state_metrics(self) -> dict[str, int]:
        """Return current state metrics for monitoring."""
        return {
            "webhook_states": len(self._webhook_states),
            "cron_states": len(self._cron_states),
            "retry_configs": len(self._retry_configs),
            "retry_states": len(self._retry_states),
            "run_workflows": len(self._run_workflows),
            "completed_workflows": len(self._completed_workflows),
            "cron_run_index": len(self._cron_run_index),
        }

    def remove_workflow(self, workflow_id: UUID) -> None:
        """Remove all state associated with a workflow."""
        self._logger.info("Removing all state for workflow %s", workflow_id)

        self._webhook_states.pop(workflow_id, None)
        self._cron_states.pop(workflow_id, None)
        self._retry_configs.pop(workflow_id, None)

        runs_to_remove = [
            run_id
            for run_id, wf_id in self._run_workflows.items()
            if wf_id == workflow_id
        ]
        for run_id in runs_to_remove:
            self._retry_states.pop(run_id, None)
            self._run_workflows.pop(run_id, None)
            self._cron_run_index.pop(run_id, None)

        self._completed_workflows[workflow_id] = datetime.now(UTC)

    def reset(self) -> None:
        """Clear all stored trigger state."""
        self._webhook_states.clear()
        self._cron_states.clear()
        self._cron_run_index.clear()
        self._retry_configs.clear()
        self._retry_states.clear()
        self._run_workflows.clear()
        self._completed_workflows.clear()
        self._last_cleanup = datetime.now(UTC)


__all__ = ["CleanupMixin"]
