"""Implementation of :class:`DataTransformNode` and transform helpers."""

from __future__ import annotations
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.data.utils import _assign_path, _extract_value
from orcheo.nodes.registry import NodeMetadata, registry


class FieldTransform(BaseModel):
    """Mapping definition used by :class:`DataTransformNode`."""

    source: str | None = Field(
        default=None, description="Dotted path pointing to the source value"
    )
    target: str = Field(description="Dotted path where the transformed value is stored")
    default: Any | None = Field(
        default=None, description="Default value used when the source is missing"
    )
    when_missing: Literal["default", "skip"] = Field(
        default="default",
        description="Control whether missing values use the default or are skipped",
    )
    transform: Literal[
        "identity",
        "string",
        "int",
        "float",
        "bool",
        "lower",
        "upper",
        "title",
        "length",
    ] = Field(
        default="identity",
        description="Optional transformation applied to the extracted value",
    )


def _transform_identity(value: Any) -> Any:
    return value


def _transform_string(value: Any) -> str:
    return "" if value is None else str(value)


def _transform_int(value: Any) -> int:
    return 0 if value is None else int(value)


def _transform_float(value: Any) -> float:
    return 0.0 if value is None else float(value)


def _transform_bool(value: Any) -> bool:
    return bool(value)


def _transform_lower(value: Any) -> Any:
    return value.lower() if isinstance(value, str) else value


def _transform_upper(value: Any) -> Any:
    return value.upper() if isinstance(value, str) else value


def _transform_title(value: Any) -> Any:
    return value.title() if isinstance(value, str) else value


def _transform_length(value: Any) -> int:
    if isinstance(value, Mapping):
        return len(value)
    if isinstance(value, str | Sequence) and not isinstance(value, bytes | bytearray):
        return len(value)
    return 0


_TRANSFORM_HANDLERS: dict[str, Callable[[Any], Any]] = {
    "identity": _transform_identity,
    "string": _transform_string,
    "int": _transform_int,
    "float": _transform_float,
    "bool": _transform_bool,
    "lower": _transform_lower,
    "upper": _transform_upper,
    "title": _transform_title,
    "length": _transform_length,
}


def _apply_transform(value: Any, transform: str) -> Any:
    """Apply the requested transformation to ``value``."""
    handler = _TRANSFORM_HANDLERS.get(transform)
    if handler is None:
        return value
    return handler(value)


@registry.register(
    NodeMetadata(
        name="DataTransformNode",
        description="Map values from an input payload into a transformed structure.",
        category="data",
    )
)
class DataTransformNode(TaskNode):
    """Apply field mappings and simple transformations to structured data."""

    input_data: Any = Field(default_factory=dict, description="Input payload")
    transforms: list[FieldTransform] = Field(
        default_factory=list,
        description="Collection of field transforms applied sequentially",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the transformed payload according to configured mappings."""
        output: dict[str, Any] = {}
        for mapping in self.transforms:
            if mapping.source is None:
                value = mapping.default
                found = mapping.when_missing != "skip"
            else:
                found, value = _extract_value(self.input_data, mapping.source)
                if not found:
                    if mapping.when_missing == "skip":
                        continue
                    value = mapping.default

            value = _apply_transform(value, mapping.transform)
            _assign_path(output, mapping.target, value)

        return {"result": output}
