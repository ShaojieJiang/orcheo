"""Base node implementation for Orcheo."""

import logging
import re
from abc import abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any, Self, cast
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
_SINGLE_TEMPLATE_PATTERN = re.compile(r"^\s*\{\{\s*([^{}]+?)\s*\}\}\s*$")
_TEMPLATE_PATTERN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


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
        """Recursively decode a value that may contain template strings.

        Identity-preserving: returns the *same* object when no resolution
        is needed, enabling cheap ``is`` checks for copy-on-write callers.
        """
        if isinstance(value, CredentialReference):
            return self._resolve_credential_reference(value)
        if isinstance(value, str):
            return self._decode_string_value(value, state)
        if isinstance(value, BaseModel):
            return self._decode_model_value(value, state)
        if isinstance(value, dict):
            return self._decode_dict_value(value, state)
        if isinstance(value, list):
            return self._decode_list_value(value, state)
        return value

    def _decode_model_value(self, value: BaseModel, state: State) -> BaseModel:
        """Decode a nested Pydantic model, returning the same object if unchanged."""
        changed: dict[str, Any] = {}
        for field_name in value.__class__.model_fields:
            original = getattr(value, field_name)
            decoded = self._decode_value(original, state)
            if decoded is not original:
                changed[field_name] = decoded
        return value.model_copy(update=changed) if changed else value

    def _decode_dict_value(self, value: dict[str, Any], state: State) -> dict[str, Any]:
        """Decode a dict, returning the same object if no values changed."""
        new_dict: dict[str, Any] = {}
        any_changed = False
        for k, v in value.items():
            decoded = self._decode_value(v, state)
            new_dict[k] = decoded
            if decoded is not v:
                any_changed = True
        return new_dict if any_changed else value

    def _decode_list_value(self, value: list[Any], state: State) -> list[Any]:
        """Decode a list, returning the same object if no items changed."""
        new_list: list[Any] = []
        any_changed = False
        for item in value:
            decoded = self._decode_value(item, state)
            new_list.append(decoded)
            if decoded is not item:
                any_changed = True
        return new_list if any_changed else value

    def _decoded_updates(self, state: State) -> dict[str, Any]:
        """Return decoded field values without mutating the runnable."""
        return {
            key: self._decode_value(value, state)
            for key, value in self.__dict__.items()
        }

    def _resolve_nested_credential_string(self, value: Any) -> Any:
        """Resolve a credential placeholder returned by template expansion."""
        if not isinstance(value, str):
            return value
        reference = parse_credential_reference(value)
        if reference is None:
            return value
        return self._resolve_credential_reference(reference)

    def _decode_string_value(
        self,
        value: str,
        state: State,
    ) -> Any:
        """Return decoded value for placeholders or state templates."""
        reference = parse_credential_reference(value)
        if reference is not None:
            return self._resolve_credential_reference(reference)
        if "{{" not in value or "}}" not in value:
            return value

        single_template_match = _SINGLE_TEMPLATE_PATTERN.fullmatch(value)
        if single_template_match is not None:
            resolved, is_resolved = self._resolve_state_template_path(
                single_template_match.group(1).strip(),
                value,
                state,
            )
            if not is_resolved:
                return value
            return self._resolve_nested_credential_string(resolved)

        def _replace(match: re.Match[str]) -> str:
            template = match.group(0)
            resolved, is_resolved = self._resolve_state_template_path(
                match.group(1).strip(),
                template,
                state,
            )
            if is_resolved:
                resolved = self._resolve_nested_credential_string(resolved)
            if not is_resolved or not isinstance(resolved, str | int | float | bool):
                return template
            return str(resolved)

        return _TEMPLATE_PATTERN.sub(_replace, value)

    def _resolve_state_template_path(
        self,
        path_str: str,
        template_text: str,
        state: State,
    ) -> tuple[Any, bool]:
        """Resolve ``path_str`` against workflow ``state``.

        Returns the resolved value and whether resolution succeeded.
        """
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
                template_text,
                part,
            )
            return None, False
        return result, True

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
        del config
        self.__dict__.update(self._decoded_updates(state))

    def _compute_run_updates(self, state: State) -> dict[str, Any]:
        """Return only the fields whose values changed during resolution.

        Subclasses may override to exclude fields from resolution (see
        ``AgentNode`` which defers history-key fields).
        """
        updates: dict[str, Any] = {}
        for key, value in self.__dict__.items():
            decoded = self._decode_value(value, state)
            if decoded is not value:
                updates[key] = decoded
        return updates

    def resolved_for_run(
        self,
        state: State,
        *,
        config: Mapping[str, Any] | None = None,
    ) -> Self:
        """Return a copy with templates resolved for the current invocation.

        Uses copy-on-write: avoids the ``model_copy()`` allocation when no
        field values actually changed during template resolution.
        """
        del config
        changed = self._compute_run_updates(state)
        if not changed:
            return self
        return cast(Self, self.model_copy(update=changed))


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
        runnable = self.resolved_for_run(state, config=config)
        result = await runnable.run(state, config)
        return runnable._serialize_result(result)

    @abstractmethod
    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Run the node."""
        pass  # pragma: no cover


class TaskNode(BaseNode):
    """Base class for all nodes that need to define their own run method."""

    async def __call__(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the node and wrap the result in a outputs key."""
        runnable = self.resolved_for_run(state, config=config)
        result = await runnable.run(state, config)
        serialized_result = runnable._serialize_result(result)
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
