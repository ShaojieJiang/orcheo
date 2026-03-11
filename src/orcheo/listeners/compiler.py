"""Workflow-graph listener compilation helpers."""

from __future__ import annotations
from typing import Any
from uuid import UUID, uuid5
from orcheo.listeners.models import ListenerPlatform, ListenerSubscription


_LISTENER_NAMESPACE = UUID("cb2512f5-f1d4-4883-bc6f-6d5c7a560fce")


def compile_listener_subscriptions(
    workflow_id: UUID,
    workflow_version_id: UUID,
    graph: dict[str, Any],
) -> list[ListenerSubscription]:
    """Compile listener subscriptions from the workflow graph index."""
    listeners = graph.get("index", {}).get("listeners", [])
    if not isinstance(listeners, list):
        return []

    subscriptions: list[ListenerSubscription] = []
    for item in listeners:
        if not isinstance(item, dict):
            continue
        node_name = str(item.get("node_name") or item.get("name") or "").strip()
        platform_value = str(item.get("platform") or "").strip().lower()
        if not node_name or not platform_value:
            continue
        try:
            platform = ListenerPlatform(platform_value)
        except ValueError:
            continue

        bot_identity_key = _derive_bot_identity_key(platform, item)
        subscription_id = uuid5(
            _LISTENER_NAMESPACE,
            f"{workflow_version_id}:{platform.value}:{node_name}:{bot_identity_key}",
        )
        config = {
            key: value
            for key, value in item.items()
            if key not in {"name", "node_name", "type", "platform"}
        }
        subscriptions.append(
            ListenerSubscription(
                id=subscription_id,
                workflow_id=workflow_id,
                workflow_version_id=workflow_version_id,
                node_name=node_name,
                platform=platform,
                bot_identity_key=bot_identity_key,
                config=config,
            )
        )
    return subscriptions


def _derive_bot_identity_key(
    platform: ListenerPlatform,
    item: dict[str, Any],
) -> str:
    explicit = item.get("bot_identity_key")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    for key in ("token", "app_id", "credential_ref"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return f"{platform.value}:{value.strip()}"
    return f"{platform.value}:{item.get('node_name') or item.get('name')}"


__all__ = ["compile_listener_subscriptions"]
