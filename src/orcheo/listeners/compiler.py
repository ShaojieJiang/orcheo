"""Workflow-graph listener compilation helpers."""

from __future__ import annotations
from typing import Any
from uuid import UUID
from orcheo.listeners.models import ListenerSubscription
from orcheo.listeners.registry import listener_registry, register_builtin_listeners
from orcheo.plugins import ensure_plugins_loaded


def compile_listener_subscriptions(
    workflow_id: UUID,
    workflow_version_id: UUID,
    graph: dict[str, Any],
) -> list[ListenerSubscription]:
    """Compile listener subscriptions from the workflow graph index."""
    register_builtin_listeners()
    ensure_plugins_loaded()
    listeners = graph.get("index", {}).get("listeners", [])
    if not isinstance(listeners, list):
        return []

    subscriptions: list[ListenerSubscription] = []
    for item in listeners:
        if not isinstance(item, dict):
            continue
        platform_value = str(item.get("platform") or "").strip().lower()
        if not platform_value:
            continue
        subscription = listener_registry.compile_subscription(
            workflow_id=workflow_id,
            workflow_version_id=workflow_version_id,
            item=item,
            platform_id=platform_value,
        )
        if subscription is not None:
            subscriptions.append(subscription)
    return subscriptions


__all__ = ["compile_listener_subscriptions"]
