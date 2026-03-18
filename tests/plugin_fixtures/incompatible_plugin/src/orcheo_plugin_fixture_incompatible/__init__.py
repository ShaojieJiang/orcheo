"""Fixture incompatible plugin."""

from orcheo.plugins import PluginAPI


class FixtureIncompatiblePlugin:
    """Minimal entry point object used by CLI plugin tests."""

    def register(self, api: PluginAPI) -> None:
        del api


plugin = FixtureIncompatiblePlugin()
