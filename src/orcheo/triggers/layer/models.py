"""Shared dataclasses for the trigger orchestration layer."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID
from orcheo.triggers.manual import ManualDispatchRun


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


__all__ = [
    "CronDispatchPlan",
    "ManualDispatchPlan",
    "StateCleanupConfig",
    "TriggerDispatch",
]
