"""Graph builder module for Orcheo."""

from __future__ import annotations
from collections.abc import Callable, Iterable, Mapping
from typing import Any
from langgraph.graph import END, START, StateGraph
from orcheo.graph.ingestion import LANGGRAPH_SCRIPT_FORMAT, load_graph_from_script
from orcheo.graph.state import State
from orcheo.nodes.registry import registry


def build_graph(graph_json: Mapping[str, Any]) -> StateGraph:
    """Build a LangGraph graph from a configuration payload."""
    if graph_json.get("format") == LANGGRAPH_SCRIPT_FORMAT:
        source = graph_json.get("source")
        if not isinstance(source, str) or not source.strip():
            msg = "Script graph configuration requires a non-empty source"
            raise ValueError(msg)
        entrypoint_value = graph_json.get("entrypoint")
        if entrypoint_value is not None and not isinstance(entrypoint_value, str):
            msg = "Entrypoint must be a string when provided"
            raise ValueError(msg)
        return load_graph_from_script(source, entrypoint=entrypoint_value)

    graph = StateGraph(State)
    nodes = list(graph_json.get("nodes", []))
    edges = list(graph_json.get("edges", []))

    for node in nodes:
        node_type = node.get("type")
        if node_type in {"START", "END"}:
            continue
        node_class = registry.get_node(str(node_type))
        if node_class is None:
            msg = f"Unknown node type: {node_type}"
            raise ValueError(msg)
        node_params = {k: v for k, v in node.items() if k != "type"}
        node_instance = node_class(**node_params)
        graph.add_node(str(node["name"]), node_instance)

    for source, target in _normalise_edges(edges):
        graph.add_edge(_normalise_vertex(source), _normalise_vertex(target))

    for branch in graph_json.get("conditional_edges", []):
        _add_conditional_edges(graph, branch)

    for parallel in graph_json.get("parallel_branches", []):
        _add_parallel_branches(graph, parallel)

    return graph


def _normalise_edges(edges: Iterable[Any]) -> list[tuple[str, str]]:
    """Normalise edge definitions into source/target pairs."""
    normalised: list[tuple[str, str]] = []
    for entry in edges:
        if isinstance(entry, Mapping):
            source = entry.get("source")
            target = entry.get("target")
        else:
            try:
                source, target = entry  # type: ignore[misc]
            except (TypeError, ValueError) as exc:
                msg = f"Invalid edge entry: {entry!r}"
                raise ValueError(msg) from exc
        if not isinstance(source, str) or not isinstance(target, str):
            msg = f"Edge endpoints must be strings: {entry!r}"
            raise ValueError(msg)
        normalised.append((source, target))
    return normalised


def _normalise_vertex(name: str) -> Any:
    """Map sentinel vertex names to LangGraph constants."""
    if name == "START":
        return START
    if name == "END":
        return END
    return name


def _add_conditional_edges(graph: StateGraph, config: Mapping[str, Any]) -> None:
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

    normalised_mapping = {
        str(key): _normalise_vertex(str(target)) for key, target in mapping.items()
    }
    resolved_default = None
    if isinstance(default_target, str) and default_target:
        resolved_default = _normalise_vertex(default_target)

    condition = _make_condition(path, normalised_mapping, resolved_default)

    graph.add_conditional_edges(
        _normalise_vertex(source),
        condition,
    )


def _add_parallel_branches(graph: StateGraph, config: Mapping[str, Any]) -> None:
    """Add fan-out/fan-in style parallel branches."""
    source = config.get("source")
    targets = config.get("targets")
    join = config.get("join")

    if not isinstance(source, str) or not source:
        msg = f"Parallel branch requires a source string: {config!r}"
        raise ValueError(msg)
    if isinstance(targets, str) or not isinstance(targets, Iterable):
        msg = f"Parallel branch requires a list of targets: {config!r}"
        raise ValueError(msg)

    normalised_source = _normalise_vertex(source)
    target_list = list(targets)
    normalised_targets = []
    for target in target_list:
        if not isinstance(target, str):
            msg = f"Parallel branch targets must be strings: {config!r}"
            raise ValueError(msg)
        normalised_targets.append(_normalise_vertex(target))
    if not normalised_targets:
        msg = f"Parallel branch targets must be strings: {config!r}"
        raise ValueError(msg)

    for target in normalised_targets:
        graph.add_edge(normalised_source, target)

    if isinstance(join, str) and join:
        join_vertex = _normalise_vertex(join)
        for target in normalised_targets:
            graph.add_edge(target, join_vertex)


def _make_condition(
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
