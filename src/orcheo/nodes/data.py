"""Data processing nodes for Orcheo workflows."""

from __future__ import annotations
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import timedelta
from typing import Any, Literal
import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


HttpMethod = Literal[
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
]


def _split_path(path: str) -> list[str]:
    """Return a dotted path split into segments."""
    parts = [segment.strip() for segment in path.split(".") if segment.strip()]
    if not parts:
        msg = "Path must contain at least one segment"
        raise ValueError(msg)
    return parts


def _extract_value(payload: Any, path: str) -> tuple[bool, Any]:
    """Return the value found at ``path`` within ``payload`` if present."""
    current = payload
    for segment in _split_path(path):
        if isinstance(current, Mapping):
            if segment not in current:
                return False, None
            current = current[segment]
            continue

        if isinstance(current, Sequence) and not isinstance(
            current, str | bytes | bytearray
        ):
            if not segment.isdigit():
                return False, None
            index = int(segment)
            if index >= len(current):
                return False, None
            current = current[index]
            continue

        return False, None

    return True, current


def _assign_path(target: dict[str, Any], path: str, value: Any) -> None:
    """Assign ``value`` into ``target`` using the dotted ``path``."""
    segments = _split_path(path)
    cursor = target
    for segment in segments[:-1]:
        existing = cursor.get(segment)
        if not isinstance(existing, dict):
            existing = {}
            cursor[segment] = existing
        cursor = existing
    cursor[segments[-1]] = value


def _deep_merge(base: dict[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
    """Deep merge ``incoming`` into ``base`` returning the merged dictionary."""
    for key, value in incoming.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), Mapping):
            base[key] = _deep_merge(dict(base[key]), value)
        else:
            base[key] = value if not isinstance(value, Mapping) else dict(value)
    return base


@registry.register(
    NodeMetadata(
        name="HttpRequestNode",
        description="Perform an HTTP request and return the response payload.",
        category="data",
    )
)
class HttpRequestNode(TaskNode):
    """Node that performs HTTP requests using ``httpx``."""

    method: HttpMethod = Field(default="GET", description="HTTP method to execute")
    url: str = Field(description="Fully-qualified request URL")
    params: dict[str, Any] | None = Field(
        default=None, description="Optional query parameters to append to the URL"
    )
    headers: dict[str, str] | None = Field(
        default=None, description="Optional HTTP headers to include"
    )
    json_body: Any | None = Field(
        default=None, description="JSON payload supplied for request bodies"
    )
    content: Any | None = Field(
        default=None,
        description="Raw bytes or text content for the request body",
    )
    data: Any | None = Field(
        default=None,
        description="Form data payload (url-encoded or multipart)",
    )
    timeout: float | None = Field(
        default=30.0, ge=0.0, description="Optional timeout in seconds for the request"
    )
    follow_redirects: bool = Field(
        default=True, description="Follow HTTP redirects returned by the server"
    )
    raise_for_status: bool = Field(
        default=False, description="Raise an error when the response is not 2xx"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the configured HTTP request."""
        request_kwargs: dict[str, Any] = {
            "method": self.method,
            "url": self.url,
            "params": self.params,
            "headers": self.headers,
            "timeout": self.timeout,
            "follow_redirects": self.follow_redirects,
        }

        if self.json_body is not None:
            request_kwargs["json"] = self.json_body
        if self.content is not None:
            request_kwargs["content"] = self.content
        if self.data is not None:
            request_kwargs["data"] = self.data

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(**request_kwargs)
        except httpx.HTTPError as exc:  # pragma: no cover - network failure guard
            msg = f"HTTP request failed: {exc!s}"
            raise ValueError(msg) from exc

        if self.raise_for_status:
            response.raise_for_status()

        parsed_json: Any | None
        try:
            parsed_json = response.json()
        except json.JSONDecodeError:
            parsed_json = None

        elapsed: float | None = None
        elapsed_source: Any | None
        try:
            elapsed_source = response.elapsed
        except RuntimeError:
            elapsed_source = response.extensions.get("elapsed")

        if isinstance(elapsed_source, timedelta):
            elapsed = elapsed_source.total_seconds()

        try:
            response_url = str(response.url)
        except RuntimeError:
            response_url = self.url

        return {
            "status_code": response.status_code,
            "reason": response.reason_phrase,
            "url": response_url,
            "headers": dict(response.headers),
            "content": response.text,
            "json": parsed_json,
            "elapsed": elapsed,
        }


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


@registry.register(
    NodeMetadata(
        name="MergeNode",
        description="Merge multiple payloads into a single aggregate structure.",
        category="data",
    )
)
class MergeNode(TaskNode):
    """Merge multiple dictionaries or lists according to a strategy."""

    items: list[Any] = Field(
        default_factory=list,
        description="Sequence of items that should be merged in order",
    )
    mode: Literal["auto", "dict", "list"] = Field(
        default="auto", description="Merge dictionaries, lists, or auto-detect"
    )
    deep: bool = Field(
        default=True, description="Perform a deep merge when handling dictionaries"
    )
    deduplicate: bool = Field(
        default=False,
        description=(
            "Remove duplicate entries when merging lists while preserving order"
        ),
    )

    def _resolve_mode(self) -> Literal["dict", "list"]:
        """Return the effective merge mode."""
        if self.mode != "auto":
            return self.mode
        first = self.items[0]
        if isinstance(first, Mapping):
            return "dict"
        if isinstance(first, Sequence) and not isinstance(
            first, str | bytes | bytearray
        ):
            return "list"
        msg = "Unable to infer merge mode; specify mode explicitly"
        raise ValueError(msg)

    def _merge_dicts(self) -> dict[str, Any]:
        """Merge mapping payloads according to configuration."""
        merged: dict[str, Any] = {}
        for item in self.items:
            if not isinstance(item, Mapping):
                msg = "All items must be mappings when merging dictionaries"
                raise ValueError(msg)
            source = dict(item)
            if self.deep:
                merged = _deep_merge(merged, source)
            else:
                merged.update(source)
        return merged

    def _merge_lists(self) -> list[Any]:
        """Merge list payloads applying optional de-duplication."""
        merged_list: list[Any] = []
        seen: set[Any] | None = set() if self.deduplicate else None
        for item in self.items:
            if not isinstance(item, Sequence) or isinstance(
                item, str | bytes | bytearray
            ):
                msg = "All items must be sequences when merging lists"
                raise ValueError(msg)
            for value in item:
                if seen is not None and value in seen:
                    continue
                if seen is not None:
                    seen.add(value)
                merged_list.append(value)
        return merged_list

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the merged payload."""
        if not self.items:
            return {"result": [] if self.mode == "list" else {}}
        mode = self._resolve_mode()
        result: dict[str, Any] | list[Any]
        if mode == "dict":
            result = self._merge_dicts()
        else:
            result = self._merge_lists()
        return {"result": result}


__all__ = [
    "HttpRequestNode",
    "JsonProcessingNode",
    "DataTransformNode",
    "MergeNode",
    "FieldTransform",
]
