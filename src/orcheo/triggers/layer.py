"""Unified trigger orchestration layer for workflow executions."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime
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


class TriggerLayer:
    """Coordinate trigger configuration, validation, and dispatch state."""

    def __init__(self) -> None:
        """Initialize trigger state stores for the layer."""
        self._webhook_states: dict[UUID, WebhookTriggerState] = {}
        self._cron_states: dict[UUID, CronTriggerState] = {}
        self._cron_run_index: dict[UUID, UUID] = {}
        self._retry_configs: dict[UUID, RetryPolicyConfig] = {}
        self._retry_states: dict[UUID, RetryPolicyState] = {}
        self._run_workflows: dict[UUID, UUID] = {}

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
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        plans: list[CronDispatchPlan] = []
        for workflow_id, state in self._cron_states.items():
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
        return plans

    def commit_cron_dispatch(self, workflow_id: UUID) -> None:
        """Advance the cron schedule after a run has been enqueued."""
        state = self._cron_states.get(workflow_id)
        if state is None:
            return

        state.consume_due()

    def register_cron_run(self, run_id: UUID) -> None:
        """Register a cron-triggered run so overlap guards are enforced."""
        workflow_id = self._run_workflows.get(run_id)
        if workflow_id is None:
            return

        state = self._cron_states.get(workflow_id)
        self._cron_run_index[run_id] = workflow_id
        if state is None:
            return

        state.register_run(run_id)

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
        resolved_runs = request.resolve_runs(
            default_workflow_version_id=default_workflow_version_id
        )
        return ManualDispatchPlan(
            triggered_by=request.trigger_label(),
            actor=request.actor,
            runs=resolved_runs,
        )

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
        self._retry_states[run_id] = RetryPolicyState(config)

    def next_retry_for_run(
        self, run_id: UUID, *, failed_at: datetime | None = None
    ) -> RetryDecision | None:
        """Return the next retry decision for the provided run."""
        state = self._retry_states.get(run_id)
        if state is None:
            return None
        decision = state.next_retry(failed_at=failed_at)
        if decision is None:
            self._retry_states.pop(run_id, None)
            self._run_workflows.pop(run_id, None)
        return decision

    def clear_retry_state(self, run_id: UUID) -> None:
        """Remove retry tracking for the specified run."""
        self._retry_states.pop(run_id, None)
        self._run_workflows.pop(run_id, None)

    # ------------------------------------------------------------------
    # Reset helpers
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Clear all stored trigger state."""
        self._webhook_states.clear()
        self._cron_states.clear()
        self._cron_run_index.clear()
        self._retry_configs.clear()
        self._retry_states.clear()
        self._run_workflows.clear()


__all__ = [
    "CronDispatchPlan",
    "ManualDispatchPlan",
    "TriggerDispatch",
    "TriggerLayer",
]
