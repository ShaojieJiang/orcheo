"""Shared attribute scaffolding for trigger layer mixins."""

from __future__ import annotations
import logging
from datetime import datetime
from uuid import UUID
from orcheo.triggers.cron import CronTriggerState
from orcheo.triggers.layer.models import StateCleanupConfig
from orcheo.triggers.retry import RetryPolicyConfig, RetryPolicyState
from orcheo.triggers.webhook import WebhookTriggerState
from orcheo.vault.oauth import CredentialHealthGuard


class TriggerLayerState:
    """State attributes that every mixin expects."""

    _logger: logging.Logger
    _cleanup_config: StateCleanupConfig
    _health_guard: CredentialHealthGuard | None
    _webhook_states: dict[UUID, WebhookTriggerState]
    _cron_states: dict[UUID, CronTriggerState]
    _cron_run_index: dict[UUID, UUID]
    _retry_configs: dict[UUID, RetryPolicyConfig]
    _retry_states: dict[UUID, RetryPolicyState]
    _run_workflows: dict[UUID, UUID]
    _completed_workflows: dict[UUID, datetime]
    _last_cleanup: datetime

    def _maybe_cleanup_states(self) -> None: ...
    def _ensure_healthy(self, workflow_id: UUID) -> None: ...


__all__ = ["TriggerLayerState"]
