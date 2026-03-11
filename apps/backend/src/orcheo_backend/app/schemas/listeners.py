"""Listener operation request and response schemas."""

from __future__ import annotations
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field
from orcheo.listeners import ListenerPlatform, ListenerSubscriptionStatus


class ListenerStatusUpdateRequest(BaseModel):
    """Payload for pause or resume operations."""

    actor: str = Field(default="system")


class ListenerHealthResponse(BaseModel):
    """Merged persisted and runtime-facing listener health payload."""

    subscription_id: UUID
    node_name: str
    platform: ListenerPlatform
    status: ListenerSubscriptionStatus
    bot_identity_key: str
    assigned_runtime: str | None = None
    lease_expires_at: datetime | None = None
    last_event_at: datetime | None = None
    last_error: str | None = None
    runtime_status: Literal[
        "starting",
        "healthy",
        "backoff",
        "stopped",
        "error",
        "unknown",
    ] = "unknown"
    runtime_detail: str | None = None
    last_polled_at: datetime | None = None
    consecutive_failures: int = 0


class ListenerAlertResponse(BaseModel):
    """Operational alert raised for a listener subscription."""

    subscription_id: UUID
    platform: ListenerPlatform
    kind: Literal["stalled_listener", "reconnect_loop", "dispatch_failure"]
    detail: str


class ListenerMetricsPlatformBreakdown(BaseModel):
    """Per-platform listener counts."""

    platform: ListenerPlatform
    total: int = 0
    healthy: int = 0
    paused: int = 0
    errors: int = 0


class ListenerMetricsResponse(BaseModel):
    """Aggregated listener metrics and active alerts."""

    workflow_id: UUID
    total_subscriptions: int
    active_subscriptions: int
    paused_subscriptions: int
    disabled_subscriptions: int
    error_subscriptions: int
    healthy_runtimes: int
    reconnecting_runtimes: int
    stalled_listeners: int
    dispatch_failures: int
    by_platform: list[ListenerMetricsPlatformBreakdown]
    alerts: list[ListenerAlertResponse]


__all__ = [
    "ListenerAlertResponse",
    "ListenerHealthResponse",
    "ListenerMetricsPlatformBreakdown",
    "ListenerMetricsResponse",
    "ListenerStatusUpdateRequest",
]
