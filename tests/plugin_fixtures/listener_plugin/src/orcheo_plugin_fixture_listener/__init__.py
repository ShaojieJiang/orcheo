"""Fixture listener plugin."""

import asyncio
from datetime import datetime
from orcheo.listeners.models import ListenerHealthSnapshot, ListenerSubscription
from orcheo.listeners.registry import ListenerMetadata, default_listener_compiler
from orcheo.plugins import PluginAPI


class FixtureListenerAdapter:
    """Minimal adapter used by plugin loader and runtime tests."""

    def __init__(
        self,
        *,
        subscription: ListenerSubscription,
        runtime_id: str,
    ) -> None:
        self.subscription = subscription
        self._runtime_id = runtime_id

    async def run(self, stop_event: asyncio.Event) -> None:
        await stop_event.wait()

    def health(self) -> ListenerHealthSnapshot:
        return ListenerHealthSnapshot(
            subscription_id=self.subscription.id,
            runtime_id=self._runtime_id,
            status="healthy",
            platform=self.subscription.platform,
            last_polled_at=datetime.now(),
        )


class FixtureListenerPlugin:
    """Minimal entry point object used by CLI plugin tests."""

    def register(self, api: PluginAPI) -> None:
        api.register_listener(
            ListenerMetadata(
                id="fixture-listener",
                display_name="Fixture Listener",
                description="Fixture plugin listener",
            ),
            default_listener_compiler,
            lambda *, repository, subscription, runtime_id: FixtureListenerAdapter(
                subscription=subscription,
                runtime_id=runtime_id,
            ),
        )


plugin = FixtureListenerPlugin()
