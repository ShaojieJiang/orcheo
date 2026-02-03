"""Convert LangGraph StateGraph instances into JSON-serialisable summaries."""

from __future__ import annotations
from typing import Any
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel
from orcheo.nodes.registry import registry


def summarise_state_graph(graph: StateGraph) -> dict[str, Any]:
    """Return a JSON-serialisable summary of the ``StateGraph`` structure."""
    nodes = [_serialise_node(name, spec.runnable) for name, spec in graph.nodes.items()]
    edges = [_normalise_edge(edge) for edge in sorted(graph.edges)]
    branches = [
        _serialise_branch(source, branch_name, branch)
        for source, branch_map in graph.branches.items()
        for branch_name, branch in branch_map.items()
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "conditional_edges": [
            branch
            for branch in branches
            if branch.get("mapping") or branch.get("default")
        ],
    }


def _serialise_node(name: str, runnable: Any) -> dict[str, Any]:
    """Return a JSON representation for a LangGraph node."""
    runnable_obj = _unwrap_runnable(runnable)
    metadata = registry.get_metadata_by_callable(runnable_obj)
    node_type = metadata.name if metadata else type(runnable_obj).__name__
    payload = {"name": name, "type": node_type}

    if isinstance(runnable_obj, BaseModel):
        node_config = runnable_obj.model_dump(
            mode="json",
            fallback=_serialise_fallback,
        )
        node_config.pop("name", None)
        payload.update(node_config)

    return payload


def _serialise_fallback(value: Any) -> Any:
    """Return a JSON-safe representation for unsupported Pydantic values."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", fallback=_serialise_fallback)
    if isinstance(value, StateGraph):
        return {"type": "StateGraph", "nodes": sorted(value.nodes.keys())}
    if isinstance(value, CompiledStateGraph):
        return {"type": "CompiledStateGraph"}
    if isinstance(value, type):
        return f"{value.__module__}.{value.__name__}"
    if isinstance(value, set):
        return [_serialise_fallback(item) for item in value]
    return repr(value)


def _unwrap_runnable(runnable: Any) -> Any:
    """Return the underlying callable stored within LangGraph wrappers."""
    if hasattr(runnable, "afunc") and isinstance(runnable.afunc, BaseModel):
        return runnable.afunc
    if hasattr(runnable, "func") and isinstance(runnable.func, BaseModel):
        return runnable.func
    return runnable


def _serialise_branch(source: str, name: str, branch: Any) -> dict[str, Any]:
    """Return metadata describing a conditional branch."""
    mapping: dict[str, str] | None = None
    ends = getattr(branch, "ends", None)
    if isinstance(ends, dict):
        mapping = {str(key): _normalise_vertex(target) for key, target in ends.items()}

    default: str | None = None
    then_target = getattr(branch, "then", None)
    if isinstance(then_target, str):
        default = _normalise_vertex(then_target)

    payload: dict[str, Any] = {
        "source": source,
        "branch": name,
    }
    if mapping:
        payload["mapping"] = mapping
    if default is not None:
        payload["default"] = default
    if hasattr(branch, "path") and getattr(branch.path, "func", None):
        payload["callable"] = getattr(branch.path.func, "__name__", "<lambda>")

    return payload


def _normalise_edge(edge: tuple[str, str]) -> tuple[str, str]:
    """Convert LangGraph sentinel edge names into public constants."""
    source, target = edge
    return (_normalise_vertex(source), _normalise_vertex(target))


def _normalise_vertex(value: str) -> str:
    """Map LangGraph sentinel vertex names to ``START``/``END``."""
    if value == "__start__":
        return "START"
    if value == "__end__":
        return "END"
    return value


__all__ = ["summarise_state_graph"]
