"""Helpers for conditional edge handling."""

from __future__ import annotations
from collections.abc import Callable, Mapping
from typing import Any
from langgraph.graph import END, StateGraph
from orcheo.graph.edges import build_edge_router
from orcheo.graph.normalization import normalise_vertex
from orcheo.graph.state import State


def add_conditional_edges(
    graph: StateGraph,
    config: Mapping[str, Any],
    edge_instances: Mapping[str, Any],
) -> None:
    """Add conditional edges enabling branching and loops."""
    source = config.get("source")
    path = config.get("path")
    mapping = config.get("mapping")
    default_target = config.get("default")

    if not isinstance(source, str) or not source:
        msg = f"Conditional edge requires a source string: {config!r}"
        raise ValueError(msg)
    if not isinstance(path, str) or not path:
        msg = f"Conditional edge requires a path string: {config!r}"
        raise ValueError(msg)
    if not isinstance(mapping, Mapping) or not mapping:
        msg = f"Conditional edge requires a non-empty mapping: {config!r}"
        raise ValueError(msg)

    if path in edge_instances:
        edge = edge_instances[path]
        router = build_edge_router(edge, mapping, default_target)
        graph.add_conditional_edges(
            normalise_vertex(source),
            router,
        )
        return

    normalised_mapping_for_condition = {
        str(key): normalise_vertex(str(target)) for key, target in mapping.items()
    }
    resolved_default = None
    if isinstance(default_target, str) and default_target:
        resolved_default = normalise_vertex(default_target)

    condition = make_condition(path, normalised_mapping_for_condition, resolved_default)

    graph.add_conditional_edges(
        normalise_vertex(source),
        condition,
    )


def make_condition(
    path: str,
    mapping: Mapping[str, Any],
    default_target: Any | None,
) -> Callable[[State], Any]:
    """Return a callable that resolves a state path to a conditional destination."""
    keys = path.split(".")

    def resolve(state: State) -> Any:
        current: Any = state
        for key in keys:
            if isinstance(current, Mapping):
                current = current.get(key)
            else:
                current = None
                break
        if isinstance(current, bool):
            condition_key = "true" if current else "false"
        elif current is None:
            condition_key = "null"
        else:
            condition_key = str(current)

        destination = mapping.get(condition_key)
        if destination is not None:
            return destination
        if default_target is not None:
            return default_target
        return END

    return resolve
