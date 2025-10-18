"""Data and logic nodes for orchestrating workflow transformations."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any
import httpx
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


async def _http_request(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    payload: Any = None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.request(method, url, headers=headers, json=payload)
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError:
            data = response.text
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": data,
        }


@registry.register(
    NodeMetadata(
        name="HttpRequest",
        description="Perform an HTTP request and return the payload.",
        category="data",
    )
)
class HttpRequestNode(TaskNode):
    """Execute an HTTP request with optional body."""

    url: str
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    payload: dict[str, Any] | None = None
    timeout_seconds: float = 5.0

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Execute the configured HTTP request."""
        return await _http_request(
            self.method,
            self.url,
            headers=self.headers,
            payload=self.payload,
            timeout=self.timeout_seconds,
        )


@registry.register(
    NodeMetadata(
        name="JsonProcess",
        description="Extract a value from JSON using a dotted path.",
        category="data",
    )
)
class JsonProcessingNode(TaskNode):
    """Return JSON values using dotted path lookup."""

    path: str
    fallback: Any = None

    async def run(self, state: State, config: Any) -> Any:
        """Extract a value from a nested JSON structure."""
        payload = state.get("results", {})
        segments = self.path.split(".")
        current: Any = payload
        try:
            for segment in segments:
                current = current[segment]
            return current
        except Exception:
            return self.fallback


@registry.register(
    NodeMetadata(
        name="DataTransform",
        description="Apply a transform to a string payload.",
        category="data",
    )
)
class DataTransformNode(TaskNode):
    """Transform values using simple deterministic operations."""

    operation: str = Field(pattern=r"^(uppercase|lowercase|title|multiply)$")
    factor: float = 1.0

    async def run(self, state: State, config: Any) -> Any:
        """Apply the configured string or numeric transformation."""
        value = state.get("results", {}).get("input")
        if self.operation == "uppercase" and isinstance(value, str):
            return value.upper()
        if self.operation == "lowercase" and isinstance(value, str):
            return value.lower()
        if self.operation == "title" and isinstance(value, str):
            return value.title()
        if self.operation == "multiply" and isinstance(value, int | float):
            return value * self.factor
        return value


@registry.register(
    NodeMetadata(
        name="IfElse",
        description="Branch based on a boolean variable in state.",
        category="logic",
    )
)
class IfElseNode(TaskNode):
    """Return branches for true/false evaluation."""

    key: str
    when_true: str
    when_false: str

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Return the target branch for downstream routing."""
        branch = state.get("results", {}).get(self.key)
        return {"branch": self.when_true if branch else self.when_false}


@registry.register(
    NodeMetadata(
        name="Switch",
        description="Select an output based on string matching.",
        category="logic",
    )
)
class SwitchNode(TaskNode):
    """Select a case from configured options."""

    key: str
    cases: dict[str, str] = Field(default_factory=dict)
    default: str | None = None

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Resolve the selected case or fallback value."""
        value = state.get("results", {}).get(self.key)
        selected = self.cases.get(str(value), self.default)
        return {"branch": selected}


@registry.register(
    NodeMetadata(
        name="Merge",
        description="Merge two dictionaries into a single payload.",
        category="logic",
    )
)
class MergeNode(TaskNode):
    """Merge dictionary payloads."""

    left_key: str
    right_key: str

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Merge dictionary inputs from two upstream nodes."""
        left = state.get("results", {}).get(self.left_key, {})
        right = state.get("results", {}).get(self.right_key, {})
        if not isinstance(left, dict) or not isinstance(right, dict):
            raise ValueError("MergeNode requires dictionary inputs")
        merged = {**left, **right}
        return merged


@registry.register(
    NodeMetadata(
        name="SetVariable",
        description="Set a value in the workflow state results.",
        category="logic",
    )
)
class SetVariableNode(TaskNode):
    """Persist a variable in the shared workflow state."""

    name: str
    value: Any

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Persist the configured value to the workflow state."""
        state.setdefault("results", {})[self.name] = self.value
        return {self.name: self.value}


__all__ = [
    "DataTransformNode",
    "HttpRequestNode",
    "IfElseNode",
    "JsonProcessingNode",
    "MergeNode",
    "SetVariableNode",
    "SwitchNode",
]
