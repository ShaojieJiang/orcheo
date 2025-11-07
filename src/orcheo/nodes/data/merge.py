"""Implementation of :class:`MergeNode`."""

from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.data.utils import _deep_merge
from orcheo.nodes.registry import NodeMetadata, registry


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
