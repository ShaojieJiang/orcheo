"""Implementation of :class:`JsonProcessingNode`."""

from __future__ import annotations
import json
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.data.utils import _extract_value
from orcheo.nodes.registry import NodeMetadata, registry


JsonOperation = Literal["parse", "stringify", "extract"]


@registry.register(
    NodeMetadata(
        name="JsonProcessingNode",
        description="Parse, stringify, or extract data from JSON payloads.",
        category="data",
    )
)
class JsonProcessingNode(TaskNode):
    """Node that applies simple JSON transformations."""

    operation: JsonOperation = Field(
        default="parse", description="Operation to perform on the JSON payload"
    )
    input_data: Any = Field(description="Input data for the JSON operation")
    path: str | None = Field(
        default=None,
        description="Dotted path used when extracting values from parsed JSON",
    )
    default: Any | None = Field(
        default=None,
        description="Fallback value returned when extraction path is missing",
    )
    indent: int | None = Field(
        default=2, description="Indentation used when stringifying JSON output"
    )
    ensure_ascii: bool = Field(
        default=False, description="Serialise strings using ASCII-only output"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the configured JSON processing operation."""
        if self.operation == "parse":
            if isinstance(self.input_data, str):
                result = json.loads(self.input_data)
            else:
                result = self.input_data
            return {"result": result}

        if self.operation == "stringify":
            result = json.dumps(
                self.input_data,
                indent=self.indent,
                ensure_ascii=self.ensure_ascii,
            )
            return {"result": result}

        if self.operation == "extract":
            if self.path is None:
                msg = "path is required when operation is 'extract'"
                raise ValueError(msg)
            data = self.input_data
            if isinstance(data, str):
                data = json.loads(data)
            found, value = _extract_value(data, self.path)
            if not found:
                value = self.default
            return {"result": value, "found": found}

        msg = f"Unsupported JSON operation: {self.operation}"
        raise ValueError(msg)
