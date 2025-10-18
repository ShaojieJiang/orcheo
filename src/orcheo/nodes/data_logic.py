"""Data processing and logic nodes for Orcheo workflows."""

from __future__ import annotations
from dataclasses import field
from typing import Any
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


def _resolve_path(state: State, path: str) -> Any:
    segments = path.split(".")
    current: Any = {
        "inputs": state.get("inputs", {}),
        "results": state.get("results", {}),
    }
    for segment in segments:
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            raise KeyError(f"Path '{path}' could not be resolved")
    return current


@registry.register(
    NodeMetadata(
        name="HttpRequest",
        description="Describe an HTTP request to execute downstream",
        category="data",
    )
)
class HttpRequestNode(TaskNode):
    """Node that emits HTTP request descriptors."""

    name: str
    url: str
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] | None = None

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return a descriptor of the HTTP request to execute."""
        return {
            "url": self.url,
            "method": self.method.upper(),
            "headers": self.headers,
            "body": self.body,
        }


@registry.register(
    NodeMetadata(
        name="JsonProcess",
        description="Extract values from JSON payloads using dotted paths",
        category="data",
    )
)
class JsonProcessNode(TaskNode):
    """Node that extracts values from state using dotted paths."""

    name: str
    path: str

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Extract a value from state using the configured path."""
        value = _resolve_path(state, self.path)
        return {"value": value}


@registry.register(
    NodeMetadata(
        name="DataTransform",
        description="Map multiple values from state into a structured payload",
        category="data",
    )
)
class DataTransformNode(TaskNode):
    """Node performing simple value mapping transforms."""

    name: str
    mappings: dict[str, str]

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Map values from state into a new dictionary."""
        transformed: dict[str, Any] = {}
        for target, path in self.mappings.items():
            transformed[target] = _resolve_path(state, path)
        return transformed


@registry.register(
    NodeMetadata(
        name="IfElse",
        description="Evaluate a boolean path and emit branch information",
        category="logic",
    )
)
class IfElseNode(TaskNode):
    """Node evaluating boolean condition paths."""

    name: str
    condition_path: str
    true_branch: str = "true"
    false_branch: str = "false"

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return branch metadata based on the evaluated condition."""
        value = _resolve_path(state, self.condition_path)
        branch = self.true_branch if bool(value) else self.false_branch
        return {"branch": branch, "condition": bool(value)}


@registry.register(
    NodeMetadata(
        name="Switch",
        description="Route execution based on a lookup table",
        category="logic",
    )
)
class SwitchNode(TaskNode):
    """Node performing switch-case routing."""

    name: str
    discriminator_path: str
    cases: dict[str, str]
    default: str = "default"

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Select a branch using the discriminator path and mapping."""
        value = str(_resolve_path(state, self.discriminator_path))
        branch = self.cases.get(value, self.default)
        return {"branch": branch, "value": value}


@registry.register(
    NodeMetadata(
        name="Merge",
        description="Merge multiple dictionaries sourced from state",
        category="data",
    )
)
class MergeNode(TaskNode):
    """Node merging dictionaries from specified state paths."""

    name: str
    sources: list[str]

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Merge dictionaries resolved from configured state paths."""
        merged: dict[str, Any] = {}
        for path in self.sources:
            value = _resolve_path(state, path)
            if not isinstance(value, dict):
                raise TypeError(f"Path '{path}' did not resolve to a dictionary")
            merged.update(value)
        return merged


@registry.register(
    NodeMetadata(
        name="SetVariable",
        description="Persist a value into the workflow results",
        category="logic",
    )
)
class SetVariableNode(TaskNode):
    """Node writing values into the workflow results map."""

    name: str
    target: str
    value_path: str

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the resolved value keyed by the configured target."""
        value = _resolve_path(state, self.value_path)
        return {self.target: value}


__all__ = [
    "DataTransformNode",
    "HttpRequestNode",
    "IfElseNode",
    "JsonProcessNode",
    "MergeNode",
    "SetVariableNode",
    "SwitchNode",
]
