"""Retry policy helpers for the trigger layer."""

from __future__ import annotations
from datetime import UTC, datetime
from uuid import UUID
from orcheo.triggers.layer.state import TriggerLayerState
from orcheo.triggers.retry import (
    RetryDecision,
    RetryPolicyConfig,
    RetryPolicyState,
)


class RetryPolicyMixin(TriggerLayerState):
    """Provide retry policy orchestration helpers."""

    def configure_retry_policy(
        self, workflow_id: UUID, config: RetryPolicyConfig
    ) -> RetryPolicyConfig:
        """Persist the retry policy configuration for a workflow."""
        self._retry_configs[workflow_id] = config.model_copy(deep=True)
        return self.get_retry_policy_config(workflow_id)

    def get_retry_policy_config(self, workflow_id: UUID) -> RetryPolicyConfig:
        """Return the retry policy configuration for the workflow."""
        config = self._retry_configs.get(workflow_id)
        if config is None:
            config = RetryPolicyConfig()
            self._retry_configs[workflow_id] = config
        return config.model_copy(deep=True)

    def track_run(self, workflow_id: UUID, run_id: UUID) -> None:
        """Track a newly created run for cron overlap and retry scheduling."""
        self._run_workflows[run_id] = workflow_id
        config = self._retry_configs.get(workflow_id)

        if config is None:
            self._logger.debug(
                "No retry policy configured for workflow %s, using defaults",
                workflow_id,
            )
            config = RetryPolicyConfig()

        self._retry_states[run_id] = RetryPolicyState(config)
        self._maybe_cleanup_states()

    def next_retry_for_run(
        self, run_id: UUID, *, failed_at: datetime | None = None
    ) -> RetryDecision | None:
        """Return the next retry decision for the provided run."""
        if run_id is None:
            raise ValueError("run_id cannot be None")

        state = self._retry_states.get(run_id)
        if state is None:
            self._logger.debug("No retry state found for run %s", run_id)
            return None

        try:
            decision = state.next_retry(failed_at=failed_at)
            if decision is None:
                self._logger.debug("Retry attempts exhausted for run %s", run_id)
                self._retry_states.pop(run_id, None)
                self._run_workflows.pop(run_id, None)
            return decision
        except Exception as exc:  # pragma: no cover - logging path
            self._logger.error(
                "Error computing retry decision for run %s: %s", run_id, exc
            )
            raise

    def clear_retry_state(self, run_id: UUID) -> None:
        """Remove retry tracking for the specified run."""
        workflow_id = self._run_workflows.pop(run_id, None)
        self._retry_states.pop(run_id, None)

        if workflow_id is not None:
            self._completed_workflows[workflow_id] = datetime.now(UTC)


__all__ = ["RetryPolicyMixin"]
