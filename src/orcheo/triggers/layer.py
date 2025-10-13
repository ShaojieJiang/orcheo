"""Unified trigger orchestration layer for workflow executions."""

from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID
from orcheo.triggers.cron import CronTriggerConfig, CronTriggerState
from orcheo.triggers.manual import ManualDispatchRequest, ManualDispatchRun
from orcheo.triggers.retry import (
    RetryDecision,
    RetryPolicyConfig,
    RetryPolicyState,
)
from orcheo.triggers.webhook import (
    WebhookRequest,
    WebhookTriggerConfig,
    WebhookTriggerState,
)


@dataclass(slots=True)
class TriggerDispatch:
    """Represents a normalized trigger dispatch payload."""

    triggered_by: str
    actor: str
    input_payload: dict[str, Any]


@dataclass(slots=True)
class ManualDispatchPlan:
    """Resolved manual dispatch plan for a workflow."""

    triggered_by: str
    actor: str
    runs: list[ManualDispatchRun]


@dataclass(slots=True)
class CronDispatchPlan:
    """Dispatch plan produced when a cron trigger is due."""

    workflow_id: UUID
    scheduled_for: datetime
    timezone: str


@dataclass(slots=True)
class StateCleanupConfig:
    """Configuration for automatic state cleanup."""

    max_retry_states: int = 1000
    max_completed_workflows: int = 500
    cleanup_interval_hours: int = 1
    completed_workflow_ttl_hours: int = 24


class TriggerLayer:
    """Coordinate trigger configuration, validation, and dispatch state."""

    def __init__(self, cleanup_config: StateCleanupConfig | None = None) -> None:
        """Initialize trigger state stores for the layer."""
        self._logger = logging.getLogger(__name__)
        self._cleanup_config = cleanup_config or StateCleanupConfig()

        self._webhook_states: dict[UUID, WebhookTriggerState] = {}
        self._cron_states: dict[UUID, CronTriggerState] = {}
        self._cron_run_index: dict[UUID, UUID] = {}
        self._retry_configs: dict[UUID, RetryPolicyConfig] = {}
        self._retry_states: dict[UUID, RetryPolicyState] = {}
        self._run_workflows: dict[UUID, UUID] = {}

        # Track completed workflows for cleanup
        self._completed_workflows: dict[UUID, datetime] = {}
        self._last_cleanup: datetime = datetime.now(UTC)

    # ------------------------------------------------------------------
    # Webhook triggers
    # ------------------------------------------------------------------
    def configure_webhook(
        self, workflow_id: UUID, config: WebhookTriggerConfig
    ) -> WebhookTriggerConfig:
        """Persist webhook configuration for the workflow and return a copy."""
        state = self._webhook_states.setdefault(workflow_id, WebhookTriggerState())
        state.update_config(config)
        return state.config

    def get_webhook_config(self, workflow_id: UUID) -> WebhookTriggerConfig:
        """Return the stored webhook configuration, creating defaults if needed."""
        state = self._webhook_states.setdefault(workflow_id, WebhookTriggerState())
        return state.config

    def prepare_webhook_dispatch(
        self, workflow_id: UUID, request: WebhookRequest
    ) -> TriggerDispatch:
        """Validate an inbound webhook request and return the dispatch payload."""
        if workflow_id is None:
            raise ValueError("workflow_id cannot be None")
        if request is None:
            raise ValueError("request cannot be None")

        try:
            state = self._webhook_states.setdefault(workflow_id, WebhookTriggerState())
            state.validate(request)

            normalized_payload = state.serialize_payload(request.payload)
            return TriggerDispatch(
                triggered_by="webhook",
                actor="webhook",
                input_payload={
                    "body": normalized_payload,
                    "headers": request.normalized_headers(),
                    "query_params": request.normalized_query(),
                    "source_ip": request.source_ip,
                },
            )
        except Exception as exc:
            self._logger.error(
                "Failed to prepare webhook dispatch for workflow %s: %s",
                workflow_id,
                exc,
            )
            raise

    # ------------------------------------------------------------------
    # Cron triggers
    # ------------------------------------------------------------------
    def configure_cron(
        self, workflow_id: UUID, config: CronTriggerConfig
    ) -> CronTriggerConfig:
        """Persist cron configuration for the workflow and return a copy."""
        state = self._cron_states.setdefault(workflow_id, CronTriggerState())
        state.update_config(config)
        return state.config

    def get_cron_config(self, workflow_id: UUID) -> CronTriggerConfig:
        """Return the stored cron configuration, creating defaults if needed."""
        state = self._cron_states.setdefault(workflow_id, CronTriggerState())
        return state.config

    def collect_due_cron_dispatches(self, *, now: datetime) -> list[CronDispatchPlan]:
        """Return cron dispatch plans that are due at the provided reference time."""
        if now is None:
            raise ValueError("now parameter cannot be None")

        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        plans: list[CronDispatchPlan] = []
        for workflow_id, state in self._cron_states.items():
            try:
                due_at = state.peek_due(now=now)
                if due_at is None or not state.can_dispatch():
                    continue
                plans.append(
                    CronDispatchPlan(
                        workflow_id=workflow_id,
                        scheduled_for=due_at,
                        timezone=state.config.timezone,
                    )
                )
            except Exception as exc:
                self._logger.error(
                    "Error checking cron dispatch for workflow %s: %s",
                    workflow_id,
                    exc,
                )
                continue
        return plans

    def commit_cron_dispatch(self, workflow_id: UUID) -> None:
        """Advance the cron schedule after a run has been enqueued."""
        if workflow_id is None:
            raise ValueError("workflow_id cannot be None")

        state = self._cron_states.get(workflow_id)
        if state is None:
            self._logger.warning(
                "Cannot commit cron dispatch for workflow %s: no cron state found",
                workflow_id,
            )
            return

        try:
            state.consume_due()
        except Exception as exc:
            self._logger.error(
                "Failed to commit cron dispatch for workflow %s: %s",
                workflow_id,
                exc,
            )
            raise

    def register_cron_run(self, run_id: UUID) -> None:
        """Register a cron-triggered run so overlap guards are enforced."""
        workflow_id = self._run_workflows.get(run_id)
        if workflow_id is None:
            self._logger.warning(
                "Cannot register cron run %s: workflow not tracked",
                run_id,
            )
            return

        self._cron_run_index[run_id] = workflow_id

        state = self._cron_states.get(workflow_id)
        if state is None:
            self._logger.warning(
                "Cannot register cron run %s: no cron state for workflow %s",
                run_id,
                workflow_id,
            )
            return

        try:
            state.register_run(run_id)
        except Exception:
            self._cron_run_index.pop(run_id, None)
            raise

    def release_cron_run(self, run_id: UUID) -> None:
        """Release overlap tracking for the provided cron run."""
        workflow_id = self._cron_run_index.pop(run_id, None)
        if workflow_id is None:
            return
        state = self._cron_states.get(workflow_id)
        if state is not None:
            state.release_run(run_id)

    # ------------------------------------------------------------------
    # Manual triggers
    # ------------------------------------------------------------------
    def prepare_manual_dispatch(
        self, request: ManualDispatchRequest, *, default_workflow_version_id: UUID
    ) -> ManualDispatchPlan:
        """Resolve manual dispatch runs and return the dispatch plan."""
        if request is None:
            raise ValueError("request cannot be None")
        if default_workflow_version_id is None:
            raise ValueError("default_workflow_version_id cannot be None")

        try:
            resolved_runs = request.resolve_runs(
                default_workflow_version_id=default_workflow_version_id
            )
            return ManualDispatchPlan(
                triggered_by=request.trigger_label(),
                actor=request.actor,
                runs=resolved_runs,
            )
        except Exception as e:
            self._logger.error(f"Failed to prepare manual dispatch: {e}")
            raise

    # ------------------------------------------------------------------
    # Retry policies
    # ------------------------------------------------------------------
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

        # Handle None config explicitly
        if config is None:
            self._logger.debug(
                "No retry policy configured for workflow %s, using defaults",
                workflow_id,
            )
            config = RetryPolicyConfig()

        self._retry_states[run_id] = RetryPolicyState(config)

        # Trigger cleanup if needed
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
        except Exception as exc:
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

    # ------------------------------------------------------------------
    # Reset helpers
    # ------------------------------------------------------------------
    def remove_workflow(self, workflow_id: UUID) -> None:
        """Remove all state associated with a workflow."""
        self._logger.info("Removing all state for workflow %s", workflow_id)

        # Remove webhook and cron states
        self._webhook_states.pop(workflow_id, None)
        self._cron_states.pop(workflow_id, None)
        self._retry_configs.pop(workflow_id, None)

        # Remove run tracking for this workflow
        runs_to_remove = [
            run_id
            for run_id, wf_id in self._run_workflows.items()
            if wf_id == workflow_id
        ]
        for run_id in runs_to_remove:
            self._retry_states.pop(run_id, None)
            self._run_workflows.pop(run_id, None)
            self._cron_run_index.pop(run_id, None)

        # Mark as completed for cleanup tracking
        self._completed_workflows[workflow_id] = datetime.now(UTC)

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

        # Also cleanup if we have too many completed workflows
        if (
            len(self._completed_workflows)
            > self._cleanup_config.max_completed_workflows
        ):
            # Remove oldest completed workflows
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


__all__ = [
    "CronDispatchPlan",
    "ManualDispatchPlan",
    "StateCleanupConfig",
    "TriggerDispatch",
    "TriggerLayer",
]
