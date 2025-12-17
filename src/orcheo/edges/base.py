"""Base edge implementation for Orcheo."""

from abc import abstractmethod
from langchain_core.runnables import RunnableConfig
from langgraph.types import Send
from orcheo.graph.state import State
from orcheo.nodes.base import BaseRunnable


class BaseEdge(BaseRunnable):
    """Base class for all edges in the flow.

    Edges are responsible for routing decisions in the workflow graph.
    They inherit variable decoding and credential resolution from BaseRunnable
    but return routing decisions instead of data transformations.
    """

    async def __call__(self, state: State, config: RunnableConfig) -> str | list[Send]:
        """Execute the edge and return the routing decision."""
        self.decode_variables(state, config=config)
        result = await self.run(state, config)
        return result

    @abstractmethod
    async def run(self, state: State, config: RunnableConfig) -> str | list[Send]:
        """Run the edge and return routing decision.

        Returns:
            Either a string indicating the next node/edge to route to,
            or a list of Send objects for dynamic fan-out patterns.
        """
        pass  # pragma: no cover


__all__ = ["BaseEdge"]
