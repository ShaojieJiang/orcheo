"""Helper utilities for constructing and routing edge nodes."""

from __future__ import annotations
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Send
from orcheo.graph.normalization import normalise_vertex
from orcheo.graph.state import State
from orcheo.nodes.registry import registry


def build_edge_nodes(edge_nodes: Iterable[Any]) -> dict[str, Any]:
    """Instantiate configured edge nodes."""
    edge_node_instances: dict[str, Any] = {}
    for edge_node in edge_nodes:
        node_type = edge_node.get("type")
        node_name = edge_node.get("name")
        if not node_name:
            msg = "Edge node must have a name"
            raise ValueError(msg)
        node_class = registry.get_node(str(node_type))
        if node_class is None:
            msg = f"Unknown edge node type: {node_type}"
            raise ValueError(msg)
        node_params = {k: v for k, v in edge_node.items() if k != "type"}
        edge_node_instances[str(node_name)] = node_class(**node_params)
    return edge_node_instances


def build_edge_node_router(
    edge_node: Callable[[State, RunnableConfig], Awaitable[Any]],
    mapping: Mapping[str, Any],
    default_target: Any | None,
) -> Callable[[State, RunnableConfig], Awaitable[Any]]:
    """Return an async router that normalises decision node outputs."""
    normalised_mapping_for_edge: dict[str, Any] = {
        str(key): normalise_vertex(str(target)) for key, target in mapping.items()
    }
    resolved_default = None
    if isinstance(default_target, str) and default_target:
        resolved_default = normalise_vertex(default_target)

    async def _route_edge_node(state: State, config: RunnableConfig) -> Any:
        result = await edge_node(state, config)
        if isinstance(result, Sequence) and not isinstance(result, str | bytes):
            return [
                _coerce_edge_node_destination(
                    item, normalised_mapping_for_edge, resolved_default
                )
                for item in result
            ]
        return _coerce_edge_node_destination(
            result, normalised_mapping_for_edge, resolved_default
        )

    return _route_edge_node


def _coerce_edge_node_destination(
    value: Any,
    mapping: Mapping[str, Any],
    default_target: Any | None,
) -> Any:
    """Return a normalised destination for an edge node result."""
    if isinstance(value, Send):
        return value
    normalised = mapping.get(str(value))
    if normalised is not None:
        return normalised
    if default_target is not None:
        return default_target
    return END
