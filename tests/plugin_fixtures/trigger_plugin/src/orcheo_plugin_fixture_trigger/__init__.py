"""Fixture trigger plugin."""

from orcheo.plugins import PluginAPI
from orcheo.triggers.registry import TriggerMetadata


class FixtureTriggerPlugin:
    """Minimal entry point object used by plugin loader tests."""

    def register(self, api: PluginAPI) -> None:
        api.register_trigger(
            TriggerMetadata(
                id="fixture-trigger",
                display_name="Fixture Trigger",
                description="Fixture plugin trigger",
            ),
            lambda **kwargs: {
                "kind": "fixture-trigger",
                "config": dict(kwargs),
            },
        )


plugin = FixtureTriggerPlugin()
