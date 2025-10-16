"""Utilities for ingesting LangGraph Python scripts."""

from __future__ import annotations
import builtins
import importlib
import inspect
from types import MappingProxyType
from typing import Any
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel
from orcheo.nodes.registry import registry


LANGGRAPH_SCRIPT_FORMAT = "langgraph-script"

_SAFE_MODULE_PREFIXES: tuple[str, ...] = (
    "langgraph",
    "orcheo",
    "typing",
    "typing_extensions",
    "collections",
    "dataclasses",
    "datetime",
    "functools",
    "itertools",
    "math",
    "operator",
    "pydantic",
)


def _create_sandbox_namespace() -> dict[str, Any]:
    """Return a namespace configured with restricted builtins for script exec."""

    def _restricted_import(
        name: str,
        globals_: dict[str, Any] | None = None,
        locals_: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        """Import ``name`` when it matches an allow-listed module prefix."""
        if level != 0:
            msg = "Relative imports are not supported in LangGraph scripts"
            raise ScriptIngestionError(msg)

        if not any(
            name == prefix or name.startswith(f"{prefix}.")
            for prefix in _SAFE_MODULE_PREFIXES
        ):
            msg = f"Import of module '{name}' is not permitted in LangGraph scripts"
            raise ScriptIngestionError(msg)

        module = importlib.import_module(name)

        # Mirror the standard ``__import__`` behaviour by returning the
        # imported module even when ``fromlist`` is provided. Attribute access
        # is handled by the Python runtime afterwards.
        return module

    safe_builtins = {
        "None": None,
        "True": True,
        "False": False,
        "NotImplemented": NotImplemented,
        "Ellipsis": Ellipsis,
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "callable": callable,
        "chr": chr,
        "classmethod": classmethod,
        "complex": complex,
        "dict": dict,
        "divmod": divmod,
        "enumerate": enumerate,
        "filter": filter,
        "float": float,
        "format": format,
        "frozenset": frozenset,
        "getattr": getattr,
        "hasattr": hasattr,
        "hash": hash,
        "hex": hex,
        "id": id,
        "int": int,
        "isinstance": isinstance,
        "issubclass": issubclass,
        "iter": iter,
        "len": len,
        "list": list,
        "map": map,
        "max": max,
        "min": min,
        "next": next,
        "object": object,
        "ord": ord,
        "pow": pow,
        "print": print,
        "property": property,
        "range": range,
        "repr": repr,
        "reversed": reversed,
        "round": round,
        "set": set,
        "setattr": setattr,
        "slice": slice,
        "sorted": sorted,
        "staticmethod": staticmethod,
        "str": str,
        "sum": sum,
        "super": super,
        "tuple": tuple,
        "type": type,
        "vars": vars,
        "zip": zip,
        "BaseException": BaseException,
        "Exception": Exception,
        "ArithmeticError": ArithmeticError,
        "AssertionError": AssertionError,
        "AttributeError": AttributeError,
        "ImportError": ImportError,
        "ModuleNotFoundError": ModuleNotFoundError,
        "IndexError": IndexError,
        "KeyError": KeyError,
        "LookupError": LookupError,
        "MemoryError": MemoryError,
        "NameError": NameError,
        "NotImplementedError": NotImplementedError,
        "RuntimeError": RuntimeError,
        "StopAsyncIteration": StopAsyncIteration,
        "StopIteration": StopIteration,
        "TypeError": TypeError,
        "ValueError": ValueError,
        "__build_class__": builtins.__build_class__,
        "__import__": _restricted_import,
    }

    namespace: dict[str, Any] = {
        "__builtins__": MappingProxyType(safe_builtins),
        "__name__": "__orcheo_ingest__",
        "__package__": None,
    }
    return namespace


class ScriptIngestionError(RuntimeError):
    """Raised when a LangGraph script cannot be converted into a workflow graph."""


def ingest_langgraph_script(
    source: str,
    *,
    entrypoint: str | None = None,
) -> dict[str, Any]:
    """Return a workflow graph payload produced from a LangGraph Python script.

    The returned payload embeds the original script alongside a lightweight
    summary of the discovered LangGraph state graph. The summary is useful for
    visualisation and quick inspection while the original script is required to
    faithfully rebuild the graph during execution.
    """
    graph = load_graph_from_script(source, entrypoint=entrypoint)
    summary = _summarise_state_graph(graph)
    return {
        "format": LANGGRAPH_SCRIPT_FORMAT,
        "source": source,
        "entrypoint": entrypoint,
        "summary": summary,
    }


def load_graph_from_script(
    source: str,
    *,
    entrypoint: str | None = None,
) -> StateGraph:
    """Execute a LangGraph Python script and return the discovered ``StateGraph``.

    Args:
        source: Python source code containing the LangGraph definition.
        entrypoint: Optional name of the variable or zero-argument callable that
            resolves to a ``StateGraph``. When omitted, the loader attempts to
            discover a single ``StateGraph`` instance defined in the module
            namespace.

    Raises:
        ScriptIngestionError: if the script cannot be executed or no graph can
            be resolved from the resulting namespace.
    """
    namespace = _create_sandbox_namespace()

    try:
        exec(compile(source, "<langgraph-script>", "exec"), namespace)
    except ScriptIngestionError:
        raise
    except Exception as exc:  # pragma: no cover - exercised via tests
        message = "Failed to execute LangGraph script"
        raise ScriptIngestionError(message) from exc

    module_name = namespace["__name__"]

    if entrypoint is not None:
        if entrypoint not in namespace:
            msg = f"Entrypoint '{entrypoint}' not found in script"
            raise ScriptIngestionError(msg)
        candidates = [namespace[entrypoint]]
    else:
        candidates = [
            value
            for value in namespace.values()
            if _is_graph_candidate(value, module_name)
        ]
        if not candidates:
            msg = "Script did not produce a LangGraph StateGraph"
            raise ScriptIngestionError(msg)

    resolved_graphs = [
        graph for candidate in candidates if (graph := _resolve_graph(candidate))
    ]

    if not resolved_graphs:
        msg = "Unable to resolve a LangGraph StateGraph from the script"
        raise ScriptIngestionError(msg)

    if entrypoint is None and len(resolved_graphs) > 1:
        msg = "Multiple StateGraph candidates discovered; specify an entrypoint"
        raise ScriptIngestionError(msg)

    return resolved_graphs[0]


def _is_graph_candidate(obj: Any, module_name: str) -> bool:
    """Return ``True`` when ``obj`` may resolve to a ``StateGraph``."""
    if isinstance(obj, StateGraph | CompiledStateGraph):
        return True

    if inspect.isfunction(obj) or inspect.iscoroutinefunction(obj):
        return getattr(obj, "__module__", "") == module_name

    return False


def _resolve_graph(obj: Any) -> StateGraph | None:
    """Return a ``StateGraph`` from the supplied object if possible."""
    if isinstance(obj, StateGraph):
        return obj

    if isinstance(obj, CompiledStateGraph):
        return obj.builder

    if callable(obj):
        signature = inspect.signature(obj)
        if any(
            parameter.default is inspect.Parameter.empty
            and parameter.kind
            not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
            for parameter in signature.parameters.values()
        ):
            return None
        try:
            result = obj()
        except Exception:  # pragma: no cover - the caller will raise a clearer error
            return None
        return _resolve_graph(result)

    return None


def _summarise_state_graph(graph: StateGraph) -> dict[str, Any]:
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
        node_config = runnable_obj.model_dump(mode="json")
        node_config.pop("name", None)
        payload.update(node_config)

    return payload


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


__all__ = [
    "LANGGRAPH_SCRIPT_FORMAT",
    "ScriptIngestionError",
    "ingest_langgraph_script",
    "load_graph_from_script",
]
