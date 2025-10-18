"""Data orchestration nodes for Orcheo workflows."""

from __future__ import annotations
from typing import Any
import httpx as _httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


class _HttpxNamespace:
    """Container exposing httpx client classes for easy monkeypatching."""

    AsyncClient = _httpx.AsyncClient


httpx = _HttpxNamespace()


@registry.register(
    NodeMetadata(
        name="HttpRequest",
        description="Execute an HTTP request and return the response payload.",
        category="data",
    )
)
class HttpRequest(TaskNode):
    """Perform HTTP requests using httpx."""

    method: str = Field(default="GET")
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, str] = Field(default_factory=dict)
    json_body: dict[str, Any] | None = None
    timeout: float = Field(default=10.0, gt=0.0)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the configured HTTP request and return response details."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                self.method,
                self.url,
                headers=self.headers,
                params=self.params,
                json=self.json_body,
            )
        try:
            body = response.json()
        except ValueError:
            body = response.text
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": body,
        }


@registry.register(
    NodeMetadata(
        name="JsonExtractor",
        description="Extract a value from the workflow results by path.",
        category="data",
    )
)
class JsonExtractor(TaskNode):
    """Extract nested values from workflow results."""

    path: list[str] = Field(default_factory=list)
    default: Any = None

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Extract a nested value from the previous node results."""
        value: Any = state["results"]
        for part in self.path:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
            if value is None:
                break
        return value if value is not None else self.default


class TransformMapping(BaseModel):
    """Defines how to map keys to expressions in the transform node."""

    target: str
    expression: str


@registry.register(
    NodeMetadata(
        name="DataTransform",
        description="Transform dictionaries using Python expressions.",
        category="data",
    )
)
class DataTransform(TaskNode):
    """Apply lightweight Python expressions to generate transformed data."""

    source_key: str
    mappings: list[TransformMapping] = Field(default_factory=list)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Compute target keys by evaluating expressions against source data."""
        source = state["results"].get(self.source_key, {})
        if not isinstance(source, dict):
            msg = f"Source '{self.source_key}' must be a dictionary"
            raise ValueError(msg)
        transformed: dict[str, Any] = {}
        safe_globals = {"__builtins__": {"len": len, "min": min, "max": max}}
        for mapping in self.mappings:
            transformed[mapping.target] = eval(  # noqa: S307 - expressions are user defined
                mapping.expression,
                safe_globals,
                {"data": source},
            )
        return transformed


__all__ = [
    "HttpRequest",
    "JsonExtractor",
    "DataTransform",
    "TransformMapping",
]
