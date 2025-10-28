"""Base node implementation for Orcheo."""

import logging
from abc import abstractmethod
from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.types import Send
from pydantic import BaseModel
from orcheo.graph.state import State
from orcheo.runtime.credentials import (
    CredentialReference,
    CredentialResolverUnavailableError,
    get_active_credential_resolver,
    parse_credential_reference,
)


logger = logging.getLogger(__name__)


class BaseNode(BaseModel):
    """Base class for all nodes in the flow."""

    name: str
    """Unique name of the node."""

    def _decode_value(self, value: Any, state: State) -> Any:
        """Recursively decode a value that may contain template strings."""
        if isinstance(value, CredentialReference):
            return self._resolve_credential_reference(value)
        if isinstance(value, str):
            return self._decode_string_value(value, state)
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

    def _decode_string_value(self, value: str, state: State) -> Any:
        """Return decoded value for placeholders or state templates."""
        reference = parse_credential_reference(value)
        if reference is not None:
            return self._resolve_credential_reference(reference)
        if "{{" not in value:
            return value

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
                continue
            logger.warning(
                "Node %s could not resolve template '%s' at segment '%s'; "
                "leaving value unchanged.",
                self.name,
                value,
                part,
            )
            return value
        return result

    def _resolve_credential_reference(self, reference: CredentialReference) -> Any:
        """Return the materialised value for ``reference`` or raise an error."""
        resolver = get_active_credential_resolver()
        if resolver is None:
            msg = (
                "Credential placeholders require an active resolver. "
                f"Node '{self.name}' attempted to access "
                f"{reference.identifier!r}"
            )
            raise CredentialResolverUnavailableError(msg)
        return resolver.resolve(reference)

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
