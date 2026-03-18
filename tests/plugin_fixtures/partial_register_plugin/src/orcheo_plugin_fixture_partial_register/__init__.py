"""Fixture plugin that registers then raises."""

from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata
from orcheo.plugins import PluginAPI


class PartialFixtureNode(TaskNode):
    """Node used to validate rollback on plugin load failure."""

    async def run(self, state: State, config: RunnableConfig) -> dict[str, str]:
        del state, config
        return {"value": "partial-register"}


class PartialRegisterPlugin:
    """Plugin entrypoint that fails after mutating registries."""

    def register(self, api: PluginAPI) -> None:
        api.register_node(
            NodeMetadata(
                name="PartialFixtureNode",
                description="Node from partial fixture plugin",
                category="plugin",
            ),
            PartialFixtureNode,
        )
        raise RuntimeError("partial registration failure")


plugin = PartialRegisterPlugin()
