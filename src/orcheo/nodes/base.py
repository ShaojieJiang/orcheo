"""Base node implementation for Orcheo."""

from abc import abstractmethod
from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.types import Send
from pydantic import BaseModel
from orcheo.graph.state import State


class BaseNode(BaseModel):
    """Base class for all nodes in the flow."""

    name: str
    """Unique name of the node."""

    def _decode_value(self, value: Any, state: State) -> Any:
        """Recursively decode a value that may contain template strings."""
        if isinstance(value, str) and "{{" in value:
            # Extract path from {{path.to.value}} format
            path_str = value.strip("{}").strip()
            path_parts = path_str.split(".")

            # Start from state["results"] for backwards compatibility
            # unless the path explicitly starts with "results"
            if path_parts[0] == "results":
                result: Any = state
            else:
                result = state.get("results", {})

            for part in path_parts:
                if isinstance(result, dict):
                    result = result.get(part)
                else:
                    return value  # Can't traverse, return original
            return result
        if isinstance(value, BaseModel):
            # Handle Pydantic models by decoding their dict representation
            for field_name in value.__class__.model_fields:
                field_value = getattr(value, field_name)
                decoded = self._decode_value(field_value, state)
                setattr(value, field_name, decoded)
            return value
        if isinstance(value, dict):
            return {k: self._decode_value(v, state) for k, v in value.items()}
        if isinstance(value, list):
            return [self._decode_value(item, state) for item in value]
        return value

    def decode_variables(self, state: State) -> None:
        """Decode the variables in attributes of the node."""
        for key, value in self.__dict__.items():
            self.__dict__[key] = self._decode_value(value, state)

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


class DecisionNode(BaseNode):
    """Base class for all decision nodes in the flow.

    Decision nodes should be used as a conditional edge in the graph, instead
    of a regular node.
    """

    async def __call__(self, state: State, config: RunnableConfig) -> str | list[Send]:
        """Execute the node and return the path to the next node."""
        self.decode_variables(state)
        path = await self.run(state, config)
        return path

    @abstractmethod
    async def run(self, state: State, config: RunnableConfig) -> str | list[Send]:
        """Run the node."""
        pass  # pragma: no cover
