"""RSS node."""

from __future__ import annotations
import feedparser
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="RSSNode",
        description="RSS node",
        category="rss",
    )
)
class RSSNode(TaskNode):
    """RSS node."""

    sources: list[str]
    """RSS sources to pull from."""

    async def run(self, state: State, config: RunnableConfig) -> list[dict]:
        """Pull the RSS updates."""
        rss_updates = []
        for source in self.sources:
            feed = feedparser.parse(source)
            rss_updates.extend(feed.entries)

        return rss_updates
