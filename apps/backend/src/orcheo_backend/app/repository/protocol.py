"""Contracts shared by repository implementations."""

from __future__ import annotations
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID
from orcheo.models.workflow import Workflow, WorkflowRun, WorkflowVersion
from orcheo.triggers.cron import CronTriggerConfig
from orcheo.triggers.manual import ManualDispatchRequest
from orcheo.triggers.retry import RetryDecision, RetryPolicyConfig
from orcheo.triggers.webhook import WebhookTriggerConfig


@dataclass(slots=True)
class VersionDiff:
    """Represents a unified diff between two workflow graphs."""

    base_version: int
    target_version: int
    diff: list[str]


@runtime_checkable
class WorkflowRepository(Protocol):
    """Protocol describing workflow repository behaviour."""

    async def list_workflows(self, *, include_archived: bool = False) -> list[Workflow]:
        """Return workflows stored within the repository."""

    async def create_workflow(
        self,
        *,
        name: str,
        slug: str | None,
        description: str | None,
        tags: Iterable[str] | None,
        actor: str,
    ) -> Workflow:
        """Persist and return a new workflow definition."""

    async def get_workflow(self, workflow_id: UUID) -> Workflow:
        """Return a single workflow by identifier."""

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
        """Mutate workflow metadata and return the updated record."""

    async def archive_workflow(self, workflow_id: UUID, *, actor: str) -> Workflow:
        """Archive the specified workflow."""

    async def publish_workflow(
        self,
        workflow_id: UUID,
        *,
        require_login: bool,
        actor: str,
    ) -> Workflow:
        """Mark the workflow as public."""

    async def revoke_publish(self, workflow_id: UUID, *, actor: str) -> Workflow:
        """Revoke public access for the workflow."""

    async def create_version(
        self,
        workflow_id: UUID,
        *,
        graph: dict[str, Any],
        metadata: dict[str, Any],
        notes: str | None,
        created_by: str,
    ) -> WorkflowVersion:
        """Persist a new workflow version for the workflow."""

    async def list_versions(self, workflow_id: UUID) -> list[WorkflowVersion]:
        """Return ordered versions for the given workflow."""

    async def get_version_by_number(
        self, workflow_id: UUID, version_number: int
    ) -> WorkflowVersion:
        """Return a workflow version by human-friendly number."""

    async def get_version(self, version_id: UUID) -> WorkflowVersion:
        """Return a workflow version by identifier."""

    async def get_latest_version(self, workflow_id: UUID) -> WorkflowVersion:
        """Return the most recently created version for the workflow."""

    async def diff_versions(
        self, workflow_id: UUID, base_version: int, target_version: int
    ) -> VersionDiff:
        """Compute a diff between two workflow versions."""

    async def create_run(
        self,
        workflow_id: UUID,
        *,
        workflow_version_id: UUID,
        triggered_by: str,
        input_payload: dict[str, Any],
        actor: str | None = None,
        runnable_config: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        """Create a workflow run for the specified version."""

    async def list_runs_for_workflow(self, workflow_id: UUID) -> list[WorkflowRun]:
        """Return runs associated with the given workflow."""

    async def get_run(self, run_id: UUID) -> WorkflowRun:
        """Return a workflow run by identifier."""

    async def mark_run_started(self, run_id: UUID, *, actor: str) -> WorkflowRun:
        """Transition a run into the running state."""

    async def mark_run_succeeded(
        self,
        run_id: UUID,
        *,
        actor: str,
        output: dict[str, Any] | None,
    ) -> WorkflowRun:
        """Mark a run as successfully completed."""

    async def mark_run_failed(
        self,
        run_id: UUID,
        *,
        actor: str,
        error: str,
    ) -> WorkflowRun:
        """Mark a run as failed with the provided error."""

    async def mark_run_cancelled(
        self,
        run_id: UUID,
        *,
        actor: str,
        reason: str | None,
    ) -> WorkflowRun:
        """Cancel a run with an optional reason."""

    async def reset(self) -> None:
        """Clear all stored workflows, versions, and runs."""

    async def configure_webhook_trigger(
        self, workflow_id: UUID, config: WebhookTriggerConfig
    ) -> WebhookTriggerConfig:
        """Store webhook trigger configuration for a workflow."""

    async def get_webhook_trigger_config(
        self, workflow_id: UUID
    ) -> WebhookTriggerConfig:
        """Return the webhook trigger configuration for a workflow."""

    async def handle_webhook_trigger(
        self,
        workflow_id: UUID,
        *,
        method: str,
        headers: Mapping[str, str],
        query_params: Mapping[str, str],
        payload: Any,
        source_ip: str | None,
    ) -> WorkflowRun:
        """Handle an inbound webhook event by enqueuing a run."""

    async def configure_cron_trigger(
        self, workflow_id: UUID, config: CronTriggerConfig
    ) -> CronTriggerConfig:
        """Persist cron trigger configuration for a workflow."""

    async def get_cron_trigger_config(self, workflow_id: UUID) -> CronTriggerConfig:
        """Return the cron trigger configuration for a workflow."""

    async def dispatch_due_cron_runs(
        self, *, now: datetime | None = None
    ) -> list[WorkflowRun]:
        """Dispatch runs for cron triggers that are due at the given time."""

    async def dispatch_manual_runs(
        self, request: ManualDispatchRequest
    ) -> list[WorkflowRun]:
        """Dispatch manual runs according to the provided request."""

    async def configure_retry_policy(
        self, workflow_id: UUID, config: RetryPolicyConfig
    ) -> RetryPolicyConfig:
        """Persist retry policy configuration for a workflow."""

    async def get_retry_policy_config(self, workflow_id: UUID) -> RetryPolicyConfig:
        """Return the retry policy configuration for a workflow."""

    async def schedule_retry_for_run(
        self, run_id: UUID, *, failed_at: datetime | None = None
    ) -> RetryDecision | None:
        """Return the next retry decision for the specified run if available."""


__all__ = ["WorkflowRepository", "VersionDiff"]
