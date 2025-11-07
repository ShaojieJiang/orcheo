"""Unified trigger orchestration layer built from modular mixins."""

from __future__ import annotations
import logging
from datetime import UTC, datetime
from uuid import UUID
from orcheo.triggers.cron import CronTriggerState
from orcheo.triggers.layer.cleanup import CleanupMixin
from orcheo.triggers.layer.cron import CronTriggerMixin
from orcheo.triggers.layer.manual import ManualDispatchMixin
from orcheo.triggers.layer.models import StateCleanupConfig
from orcheo.triggers.layer.retry import RetryPolicyMixin
from orcheo.triggers.layer.webhook import WebhookTriggerMixin
from orcheo.triggers.retry import RetryPolicyConfig, RetryPolicyState
from orcheo.triggers.webhook import WebhookTriggerState
from orcheo.vault.oauth import CredentialHealthError, CredentialHealthGuard


class TriggerLayer(
    CleanupMixin,
    WebhookTriggerMixin,
    CronTriggerMixin,
    ManualDispatchMixin,
    RetryPolicyMixin,
):
    """Coordinate trigger configuration, validation, and dispatch state."""

    def __init__(
        self,
        cleanup_config: StateCleanupConfig | None = None,
        health_guard: CredentialHealthGuard | None = None,
    ) -> None:
        """Instantiate the trigger layer and initialize state stores."""
        self._logger = logging.getLogger(__name__)
        self._cleanup_config = cleanup_config or StateCleanupConfig()
        self._health_guard = health_guard

        self._webhook_states: dict[UUID, WebhookTriggerState] = {}
        self._cron_states: dict[UUID, CronTriggerState] = {}
        self._cron_run_index: dict[UUID, UUID] = {}
        self._retry_configs: dict[UUID, RetryPolicyConfig] = {}
        self._retry_states: dict[UUID, RetryPolicyState] = {}
        self._run_workflows: dict[UUID, UUID] = {}

        self._completed_workflows: dict[UUID, datetime] = {}
        self._last_cleanup: datetime = datetime.now(UTC)

    def set_health_guard(self, guard: CredentialHealthGuard | None) -> None:
        """Attach a credential health guard used to gate dispatch."""
        self._health_guard = guard

    def _ensure_healthy(self, workflow_id: UUID) -> None:
        if self._health_guard is None:
            return
        if self._health_guard.is_workflow_healthy(workflow_id):
            return
        report = self._health_guard.get_report(workflow_id)
        if report is None:
            return
        raise CredentialHealthError(report)


__all__ = ["TriggerLayer"]
