"""Fixture node plugin."""

from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata
from orcheo.plugins import PluginAPI


class FixturePluginNode(TaskNode):
    """Minimal node used by plugin loader tests."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, str]:
        del state, config
        return {"value": "fixture-node"}


class FixtureNodePlugin:
    """Minimal entry point object used by CLI plugin tests."""

    def register(self, api: PluginAPI) -> None:
        api.register_node(
            NodeMetadata(
                name="FixturePluginNode",
                description="Fixture plugin node",
                category="plugin",
            ),
            FixturePluginNode,
        )


plugin = FixtureNodePlugin()
