"""Base node implementation for Orcheo."""

import logging
from abc import abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel
from orcheo.graph.state import State
from orcheo.nodes.registry import NodeMetadata, registry
from orcheo.runtime.credentials import (
    CredentialReference,
    CredentialResolverUnavailableError,
    get_active_credential_resolver,
    parse_credential_reference,
)


logger = logging.getLogger(__name__)


class BaseRunnable(BaseModel):
    """Base class for all runnables in Orcheo (nodes and edges).

    Provides common functionality for variable decoding, credential resolution,
    and state management. Does not include tool execution methods, which are
    specific to nodes.
    """

    name: str
    """Unique name of the runnable."""

    def _decode_value(
        self,
        value: Any,
        state: State,
    ) -> Any:
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

        result: Any = state
        for index, part in enumerate(path_parts):
            if isinstance(result, dict) and part in result:
                result = result.get(part)
                continue
            if isinstance(result, BaseModel) and hasattr(result, part):
                result = getattr(result, part)
                continue
            fallback = self._fallback_to_results(path_parts, index, state)
            if fallback is not None:
                result = fallback
                continue
            logger.warning(
                "Runnable %s could not resolve template '%s' at segment '%s'; "
                "leaving value unchanged.",
                self.name,
                value,
                part,
            )
            return value
        return result

    @staticmethod
    def _fallback_to_results(
        path_parts: list[str],
        index: int,
        state: State,
    ) -> Any | None:
        """Return a fallback lookup within ``state['results']`` when applicable."""
        if index != 0 or path_parts[0] == "results":
            return None
        results = state.get("results")
        if not isinstance(results, dict):
            return None
        return results.get(path_parts[index])

    def _resolve_credential_reference(self, reference: CredentialReference) -> Any:
        """Return the materialised value for ``reference`` or raise an error."""
        resolver = get_active_credential_resolver()
        if resolver is None:
            msg = (
                "Credential placeholders require an active resolver. "
                f"Runnable '{self.name}' attempted to access "
                f"{reference.identifier!r}"
            )
            raise CredentialResolverUnavailableError(msg)
        return resolver.resolve(reference)

    def decode_variables(
        self,
        state: State,
        *,
        config: Mapping[str, Any] | None = None,
    ) -> None:
        """Decode the variables in attributes of the runnable."""
        if config is not None and isinstance(state, dict):
            state.setdefault("config", dict(config))
        for key, value in self.__dict__.items():
            self.__dict__[key] = self._decode_value(value, state)


class BaseNode(BaseRunnable):
    """Base class for all nodes in the flow.

    Inherits variable decoding and credential resolution from BaseRunnable,
    and adds tool execution methods specific to nodes.
    """

    def tool_run(self, *args: Any, **kwargs: Any) -> Any:
        """Run the node as a tool."""
        pass  # pragma: no cover

    async def tool_arun(self, *args: Any, **kwargs: Any) -> Any:
        """Async run the node as a tool."""
        pass  # pragma: no cover

    def _serialize_result(self, value: Any) -> Any:
        """Convert Pydantic models inside outputs into serializable primitives."""
        if isinstance(value, BaseModel):
            computed_fields = getattr(
                value.__class__, "__pydantic_computed_fields__", {}
            )
            computed_keys = {
                field.alias or name for name, field in computed_fields.items()
            }
            dumped = value.model_dump()
            for key in computed_keys:  # pragma: no branch
                if key in dumped:
                    dumped.pop(key)
            return self._serialize_result(dumped)
        if isinstance(value, Mapping):
            return {key: self._serialize_result(val) for key, val in value.items()}
        if isinstance(value, tuple):
            return tuple(self._serialize_result(item) for item in value)
        if isinstance(value, Sequence) and not isinstance(
            value, str | bytes | bytearray
        ):
            return [self._serialize_result(item) for item in value]
        return value


class AINode(BaseNode):
    """Base class for all AI nodes in the flow."""

    async def __call__(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the node and wrap the result in a messages key."""
        self.decode_variables(state, config=config)
        result = await self.run(state, config)
        return self._serialize_result(result)

    @abstractmethod
    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Run the node."""
        pass  # pragma: no cover


class TaskNode(BaseNode):
    """Base class for all nodes that need to define their own run method."""

    async def __call__(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the node and wrap the result in a outputs key."""
        self.decode_variables(state, config=config)
        result = await self.run(state, config)
        serialized_result = self._serialize_result(result)
        return {"results": {self.name: serialized_result}}

    @abstractmethod
    async def run(
        self, state: State, config: RunnableConfig
    ) -> dict[str, Any] | list[Any]:
        """Run the node."""
        pass  # pragma: no cover


@registry.register(
    NodeMetadata(
        name="NoOpTaskNode",
        description=(
            "A no-op node for developers to use as a template for custom nodes. "
            "Do not use this node directly, but inherit from this with your own "
            "`run` method."
        ),
        category="base",
    )
)
class NoOpTaskNode(TaskNode):
    """No-op concrete task node for developer discovery and scaffolding."""

    async def run(
        self, state: State, config: RunnableConfig
    ) -> dict[str, Any] | list[Any]:
        """Run the no-op task node and return an empty payload."""
        del state, config
        return {}


__all__ = ["BaseRunnable", "BaseNode", "AINode", "TaskNode", "NoOpTaskNode"]
