"""Utilities for rendering workflow graphs as Mermaid diagrams."""

from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any


def _mermaid_from_graph(graph: Mapping[str, Any]) -> str:
    """Render Mermaid definition for the provided workflow graph."""
    if isinstance(graph, Mapping):
        summary = graph.get("summary")
        if isinstance(summary, Mapping):
            return _compiled_mermaid(summary)
    return _compiled_mermaid(graph)


def _compiled_mermaid(graph: Mapping[str, Any]) -> str:
    from langgraph.graph import END, START, StateGraph

    nodes = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))

    node_names = _collect_node_names(nodes)
    normalised_edges = _collect_edges(edges, node_names)

    stub: StateGraph[Any] = StateGraph(dict)  # type: ignore[type-var]
    for name in sorted(node_names):
        stub.add_node(name, _identity_state)  # type: ignore[type-var]

    compiled_edges: list[tuple[Any, Any]] = []
    for source, target in normalised_edges:
        try:
            compiled_edges.append(
                (
                    _normalise_vertex(source, START, END),
                    _normalise_vertex(target, START, END),
                )
            )
        except ValueError:  # pragma: no cover - handled via continue
            continue

    if not compiled_edges:
        if node_names:
            compiled_edges.append((START, sorted(node_names)[0]))
        else:
            compiled_edges.append((START, END))
    elif not any(source is START for source, _ in compiled_edges):
        targets = {target for _, target in compiled_edges}
        for candidate in sorted(node_names):
            if candidate not in targets:
                compiled_edges.append((START, candidate))
                break
        else:
            compiled_edges.append((START, compiled_edges[0][0]))

    for source, target in compiled_edges:
        stub.add_edge(source, target)

    compiled = stub.compile()
    return compiled.get_graph().draw_mermaid()


def _identity_state(state: dict[str, Any], *_: Any, **__: Any) -> dict[str, Any]:
    return state


def _collect_node_names(nodes: Sequence[Any]) -> set[str]:
    names: set[str] = set()
    for node in nodes:
        identifier = _node_identifier(node)
        if not identifier:
            continue
        if identifier.upper() in {"START", "END"}:
            continue
        names.add(identifier)
    return names


def _collect_edges(edges: Sequence[Any], node_names: set[str]) -> list[tuple[Any, Any]]:
    pairs: list[tuple[Any, Any]] = []
    for edge in edges:
        resolved = _resolve_edge(edge)
        if not resolved:
            continue
        source, target = resolved
        pairs.append((source, target))
        _register_endpoint(node_names, source)
        _register_endpoint(node_names, target)
    return pairs


def _node_identifier(node: Any) -> str | None:
    if isinstance(node, Mapping):
        raw = (
            node.get("id") or node.get("name") or node.get("label") or node.get("type")
        )
        if raw is None:
            return None
        return str(raw)
    if node is None:
        return None
    return str(node)


def _resolve_edge(edge: Any) -> tuple[Any, Any] | None:
    if isinstance(edge, Mapping):
        source = edge.get("from") or edge.get("source")
        target = edge.get("to") or edge.get("target")
    elif isinstance(edge, Sequence):
        if isinstance(edge, (str, bytes)):  # noqa: UP038
            return None
        if len(edge) != 2:
            return None
        source, target = edge
    else:
        return None
    if not source or not target:
        return None
    return source, target


def _register_endpoint(node_names: set[str], endpoint: Any) -> None:
    text = str(endpoint)
    if text.upper() in {"START", "END"}:
        return
    node_names.add(text)


def _normalise_vertex(value: Any, start: Any, end: Any) -> Any:
    text = str(value)
    upper = text.upper()
    if upper == "START":
        return start
    if upper == "END":
        return end
    return text


__all__ = [
    "_mermaid_from_graph",
    "_compiled_mermaid",
    "_collect_node_names",
    "_collect_edges",
    "_node_identifier",
    "_resolve_edge",
    "_register_endpoint",
    "_normalise_vertex",
    "_identity_state",
]
