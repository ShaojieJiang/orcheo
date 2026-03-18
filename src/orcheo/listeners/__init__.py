"""Listener-plane exports."""

from __future__ import annotations
from typing import Any
from uuid import UUID
from orcheo.listeners.discord import (
    DefaultDiscordGatewayConnector,
    DefaultDiscordGatewayHttpClient,
    DiscordGatewayAdapter,
    DiscordGatewayConnection,
    DiscordGatewayConnector,
    DiscordGatewayHttpClient,
    DiscordGatewayInfo,
    DiscordGatewaySessionStartLimit,
    discord_intents_bitmask,
    normalize_discord_event,
)
from orcheo.listeners.models import (
    ListenerCursor,
    ListenerDedupeRecord,
    ListenerDispatchMessage,
    ListenerDispatchPayload,
    ListenerHealthSnapshot,
    ListenerPlatform,
    ListenerSubscription,
    ListenerSubscriptionStatus,
)
from orcheo.listeners.qq import (
    DefaultQQAccessTokenHttpClient,
    DefaultQQAccessTokenProvider,
    DefaultQQGatewayConnector,
    DefaultQQGatewayHttpClient,
    QQAccessTokenHttpClient,
    QQAccessTokenPayload,
    QQAccessTokenProvider,
    QQGatewayAdapter,
    QQGatewayConnection,
    QQGatewayConnector,
    QQGatewayHttpClient,
    QQGatewayInfo,
    QQGatewaySessionStartLimit,
    normalize_qq_event,
    qq_intents_bitmask,
)
from orcheo.listeners.registry import (
    ListenerMetadata,
    ListenerRegistry,
    default_listener_compiler,
    listener_registry,
    register_builtin_listeners,
)
from orcheo.listeners.supervisor import ListenerAdapter, ListenerSupervisor
from orcheo.listeners.telegram import (
    DefaultTelegramPollingClient,
    TelegramPollingAdapter,
    TelegramPollingClient,
    normalize_telegram_update,
)


def compile_listener_subscriptions(
    workflow_id: UUID,
    workflow_version_id: UUID,
    graph: dict[str, Any],
) -> list[ListenerSubscription]:
    """Compile listener subscriptions without importing plugin code eagerly."""
    from orcheo.listeners.compiler import (
        compile_listener_subscriptions as _compile_listener_subscriptions,
    )

    return _compile_listener_subscriptions(workflow_id, workflow_version_id, graph)


register_builtin_listeners()


__all__ = [
    "compile_listener_subscriptions",
    "DefaultDiscordGatewayConnector",
    "DefaultDiscordGatewayHttpClient",
    "DefaultQQAccessTokenHttpClient",
    "DefaultQQAccessTokenProvider",
    "DefaultQQGatewayConnector",
    "DefaultQQGatewayHttpClient",
    "ListenerCursor",
    "ListenerDedupeRecord",
    "ListenerDispatchMessage",
    "ListenerDispatchPayload",
    "ListenerHealthSnapshot",
    "ListenerMetadata",
    "ListenerPlatform",
    "ListenerRegistry",
    "ListenerAdapter",
    "DiscordGatewayAdapter",
    "DiscordGatewayConnection",
    "DiscordGatewayConnector",
    "DiscordGatewayHttpClient",
    "DiscordGatewayInfo",
    "DiscordGatewaySessionStartLimit",
    "QQAccessTokenHttpClient",
    "QQAccessTokenPayload",
    "QQAccessTokenProvider",
    "QQGatewayAdapter",
    "QQGatewayConnection",
    "QQGatewayConnector",
    "QQGatewayHttpClient",
    "QQGatewayInfo",
    "QQGatewaySessionStartLimit",
    "ListenerSupervisor",
    "default_listener_compiler",
    "listener_registry",
    "register_builtin_listeners",
    "ListenerSubscription",
    "ListenerSubscriptionStatus",
    "DefaultTelegramPollingClient",
    "TelegramPollingAdapter",
    "TelegramPollingClient",
    "discord_intents_bitmask",
    "normalize_qq_event",
    "normalize_discord_event",
    "normalize_telegram_update",
    "qq_intents_bitmask",
]
