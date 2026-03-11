"""Listener health, control, and metrics routes."""

from __future__ import annotations
from datetime import timedelta
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status
from orcheo.listeners import (
    ListenerHealthSnapshot,
    ListenerSubscription,
    ListenerSubscriptionStatus,
)
from orcheo.models.base import _utcnow
from orcheo_backend.app.dependencies import (
    ListenerRuntimeStoreDep,
    RepositoryDep,
    resolve_workflow_ref_id,
)
from orcheo_backend.app.errors import raise_not_found
from orcheo_backend.app.repository import WorkflowNotFoundError
from orcheo_backend.app.schemas.listeners import (
    ListenerAlertResponse,
    ListenerHealthResponse,
    ListenerMetricsPlatformBreakdown,
    ListenerMetricsResponse,
    ListenerStatusUpdateRequest,
)


router = APIRouter()


def _merge_listener_health(
    subscription: ListenerSubscription,
    snapshot: ListenerHealthSnapshot | None,
) -> ListenerHealthResponse:
    """Merge persisted subscription state with live runtime health."""
    runtime_status: Literal[
        "starting", "healthy", "backoff", "stopped", "error", "unknown"
    ] = "unknown"
    runtime_detail: str | None = None
    last_polled_at = None
    consecutive_failures = 0
    if snapshot is not None:
        runtime_status = snapshot.status
        runtime_detail = snapshot.detail
        last_polled_at = snapshot.last_polled_at
        consecutive_failures = snapshot.consecutive_failures

    if subscription.status == ListenerSubscriptionStatus.ERROR:
        runtime_status = "error"
    return ListenerHealthResponse(
        subscription_id=subscription.id,
        node_name=subscription.node_name,
        platform=subscription.platform,
        status=subscription.status,
        bot_identity_key=subscription.bot_identity_key,
        assigned_runtime=subscription.assigned_runtime,
        lease_expires_at=subscription.lease_expires_at,
        last_event_at=subscription.last_event_at,
        last_error=subscription.last_error,
        runtime_status=runtime_status,
        runtime_detail=runtime_detail,
        last_polled_at=last_polled_at,
        consecutive_failures=consecutive_failures,
    )


async def _get_workflow_listener(
    repository: RepositoryDep,
    workflow_id: UUID,
    subscription_id: UUID,
) -> ListenerSubscription:
    """Return one workflow-scoped listener subscription."""
    try:
        subscription = await repository.get_listener_subscription(subscription_id)
    except WorkflowNotFoundError as exc:
        raise_not_found("Listener subscription not found", exc)
    if subscription.workflow_id != workflow_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listener subscription not found for workflow.",
        )
    return subscription


def _build_listener_alerts(
    items: list[ListenerHealthResponse],
    *,
    stall_threshold_seconds: int,
) -> list[ListenerAlertResponse]:
    """Derive operational alerts from listener state."""
    alerts: list[ListenerAlertResponse] = []
    now = _utcnow()
    stalled_before = now - timedelta(seconds=stall_threshold_seconds)
    for item in items:
        if (
            item.runtime_status in {"healthy", "starting"}
            and item.last_polled_at is not None
            and item.last_polled_at < stalled_before
        ):
            alerts.append(
                ListenerAlertResponse(
                    subscription_id=item.subscription_id,
                    platform=item.platform,
                    kind="stalled_listener",
                    detail="Listener runtime has not reported a recent poll heartbeat.",
                )
            )
        if item.runtime_status == "backoff" and item.consecutive_failures >= 3:
            alerts.append(
                ListenerAlertResponse(
                    subscription_id=item.subscription_id,
                    platform=item.platform,
                    kind="reconnect_loop",
                    detail="Listener runtime is repeatedly reconnecting.",
                )
            )
        if item.last_error:
            alerts.append(
                ListenerAlertResponse(
                    subscription_id=item.subscription_id,
                    platform=item.platform,
                    kind="dispatch_failure",
                    detail=item.last_error,
                )
            )
    return alerts


@router.get(
    "/workflows/{workflow_ref}/listeners",
    response_model=list[ListenerHealthResponse],
)
async def list_workflow_listeners(
    workflow_ref: str,
    repository: RepositoryDep,
    runtime_store: ListenerRuntimeStoreDep,
) -> list[ListenerHealthResponse]:
    """Return listener subscriptions enriched with live runtime health."""
    workflow_uuid = await resolve_workflow_ref_id(repository, workflow_ref)
    try:
        await repository.get_workflow(workflow_uuid)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)

    snapshots = {
        snapshot.subscription_id: snapshot for snapshot in runtime_store.list_health()
    }
    subscriptions = await repository.list_listener_subscriptions(
        workflow_id=workflow_uuid
    )
    return [
        _merge_listener_health(subscription, snapshots.get(subscription.id))
        for subscription in subscriptions
    ]


@router.get(
    "/workflows/{workflow_ref}/listeners/metrics",
    response_model=ListenerMetricsResponse,
)
async def get_workflow_listener_metrics(
    workflow_ref: str,
    repository: RepositoryDep,
    runtime_store: ListenerRuntimeStoreDep,
    stall_threshold_seconds: int = Query(default=180, ge=1, le=3600),
) -> ListenerMetricsResponse:
    """Return aggregated listener metrics and derived alerts."""
    workflow_uuid = await resolve_workflow_ref_id(repository, workflow_ref)
    try:
        await repository.get_workflow(workflow_uuid)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)

    snapshots = {
        snapshot.subscription_id: snapshot for snapshot in runtime_store.list_health()
    }
    items = [
        _merge_listener_health(subscription, snapshots.get(subscription.id))
        for subscription in await repository.list_listener_subscriptions(
            workflow_id=workflow_uuid
        )
    ]
    alerts = _build_listener_alerts(
        items,
        stall_threshold_seconds=stall_threshold_seconds,
    )
    by_platform: dict[str, ListenerMetricsPlatformBreakdown] = {}
    for item in items:
        key = item.platform.value
        breakdown = by_platform.setdefault(
            key,
            ListenerMetricsPlatformBreakdown(platform=item.platform),
        )
        breakdown.total += 1
        if item.status == ListenerSubscriptionStatus.PAUSED:
            breakdown.paused += 1
        if item.runtime_status == "healthy":
            breakdown.healthy += 1
        if item.status == ListenerSubscriptionStatus.ERROR or item.last_error:
            breakdown.errors += 1

    return ListenerMetricsResponse(
        workflow_id=workflow_uuid,
        total_subscriptions=len(items),
        active_subscriptions=sum(
            1 for item in items if item.status == ListenerSubscriptionStatus.ACTIVE
        ),
        paused_subscriptions=sum(
            1 for item in items if item.status == ListenerSubscriptionStatus.PAUSED
        ),
        disabled_subscriptions=sum(
            1 for item in items if item.status == ListenerSubscriptionStatus.DISABLED
        ),
        error_subscriptions=sum(
            1 for item in items if item.status == ListenerSubscriptionStatus.ERROR
        ),
        healthy_runtimes=sum(1 for item in items if item.runtime_status == "healthy"),
        reconnecting_runtimes=sum(
            1 for item in items if item.runtime_status == "backoff"
        ),
        stalled_listeners=sum(
            1 for alert in alerts if alert.kind == "stalled_listener"
        ),
        dispatch_failures=sum(
            1 for alert in alerts if alert.kind == "dispatch_failure"
        ),
        by_platform=list(by_platform.values()),
        alerts=alerts,
    )


@router.post(
    "/workflows/{workflow_ref}/listeners/{subscription_id}/pause",
    response_model=ListenerHealthResponse,
)
async def pause_workflow_listener(
    workflow_ref: str,
    subscription_id: UUID,
    request: ListenerStatusUpdateRequest,
    repository: RepositoryDep,
    runtime_store: ListenerRuntimeStoreDep,
) -> ListenerHealthResponse:
    """Pause one active listener subscription."""
    workflow_uuid = await resolve_workflow_ref_id(repository, workflow_ref)
    await _get_workflow_listener(repository, workflow_uuid, subscription_id)
    updated = await repository.update_listener_subscription_status(
        subscription_id,
        status=ListenerSubscriptionStatus.PAUSED,
        actor=request.actor,
    )
    return _merge_listener_health(updated, runtime_store.get_health(subscription_id))


@router.post(
    "/workflows/{workflow_ref}/listeners/{subscription_id}/resume",
    response_model=ListenerHealthResponse,
)
async def resume_workflow_listener(
    workflow_ref: str,
    subscription_id: UUID,
    request: ListenerStatusUpdateRequest,
    repository: RepositoryDep,
    runtime_store: ListenerRuntimeStoreDep,
) -> ListenerHealthResponse:
    """Resume a paused listener subscription."""
    workflow_uuid = await resolve_workflow_ref_id(repository, workflow_ref)
    await _get_workflow_listener(repository, workflow_uuid, subscription_id)
    updated = await repository.update_listener_subscription_status(
        subscription_id,
        status=ListenerSubscriptionStatus.ACTIVE,
        actor=request.actor,
    )
    return _merge_listener_health(updated, runtime_store.get_health(subscription_id))


__all__ = [
    "get_workflow_listener_metrics",
    "list_workflow_listeners",
    "pause_workflow_listener",
    "resume_workflow_listener",
    "router",
]
