"""Base node implementation for Orcheo."""

from abc import abstractmethod
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel
from orcheo.graph.state import State


class BaseNode(BaseModel):
    """Base class for all nodes in the flow."""

    name: str
    """Unique name of the node."""

    def decode_variables(self, state: State) -> None:
        """Decode the variables in attributes of the node."""
        for key, value in self.__dict__.items():
            if isinstance(value, str) and "{{" in value:
                # Extract path from {{path.to.value}} format
                path = value.strip("{}").split(".")
                result = state["results"]
                for part in path:
                    result = result[part]
                self.__dict__[key] = result

    def tool_run(self, *args: Any, **kwargs: Any) -> Any:
        """Run the node as a tool."""
        pass  # pragma: no cover

    async def tool_arun(self, *args: Any, **kwargs: Any) -> Any:
        """Async run the node as a tool."""
        pass  # pragma: no cover


class AINode(BaseNode):
    """Base class for all AI nodes in the flow."""

    async def __call__(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the node and wrap the result in a messages key."""
        self.decode_variables(state)
        result = await self.run(state, config)
        result["results"] = {self.name: result["messages"]}
        return result

    @abstractmethod
    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Run the node."""
        pass  # pragma: no cover


class TaskNode(BaseNode):
    """Base class for all non-AI task nodes in the flow."""

    async def __call__(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the node and wrap the result in a outputs key."""
        self.decode_variables(state)
        result = await self.run(state, config)
        return {"results": {self.name: result}}

    @abstractmethod
    async def run(
        self, state: State, config: RunnableConfig
    ) -> dict[str, Any] | list[Any]:
        """Run the node."""
        pass  # pragma: no cover
