"""Base node implementation for Orcheo."""

from abc import abstractmethod
from collections.abc import Mapping
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel
from orcheo.graph.state import State


class BaseNode(BaseModel):
    """Base class for all nodes in the flow."""

    name: str
    """Unique name of the node."""

    def decode_variables(self, state: State) -> None:
        """Decode template variables in string attributes using workflow state."""
        results: Mapping[str, Any] | None = getattr(state, "results", None)
        if not isinstance(results, Mapping):
            candidate: Any | None = None
            try:  # pragma: no branch - fallback for mapping-like states
                candidate = state["results"]  # type: ignore[index]
            except Exception:  # pragma: no cover - defensive access
                candidate = None
            if isinstance(candidate, Mapping):
                results = candidate
            else:
                return

        for field_name in self.model_fields:
            value = getattr(self, field_name)
            if not isinstance(value, str):
                continue
            resolved = self._resolve_template(value=value, results=results)
            if resolved is not None:
                setattr(self, field_name, resolved)

    def _resolve_template(
        self, *, value: str, results: Mapping[str, Any]
    ) -> Any | None:
        """Return the resolved value for the template expression."""

        expression = value.strip()
        if not (expression.startswith("{{") and expression.endswith("}}")):
            return None
        path = expression[2:-2].strip()
        if not path:
            return None
        segments = [segment for segment in path.split(".") if segment]
        current: Any = results
        for segment in segments:
            if isinstance(current, Mapping) and segment in current:
                current = current[segment]
            else:
                return None
        return current

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
