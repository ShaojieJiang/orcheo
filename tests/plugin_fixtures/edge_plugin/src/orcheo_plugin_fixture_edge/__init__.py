"""Fixture edge plugin."""

from langchain_core.runnables import RunnableConfig
from orcheo.edges.base import BaseEdge
from orcheo.edges.registry import EdgeMetadata
from orcheo.graph.state import State
from orcheo.plugins import PluginAPI


class FixturePluginEdge(BaseEdge):
    """Minimal edge used by plugin loader tests."""

    async def run(self, state: State, config: RunnableConfig) -> str:
        del state, config
        return "default"


class FixtureEdgePlugin:
    """Minimal entry point object used by CLI plugin tests."""

    def register(self, api: PluginAPI) -> None:
        api.register_edge(
            EdgeMetadata(
                name="FixturePluginEdge",
                description="Fixture plugin edge",
                category="plugin",
            ),
            FixturePluginEdge,
        )


plugin = FixtureEdgePlugin()
