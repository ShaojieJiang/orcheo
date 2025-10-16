"""Utilities for ingesting LangGraph Python scripts."""

from __future__ import annotations
import builtins
import contextlib
import importlib
import inspect
import signal
import sys
import threading
import time
from collections.abc import Callable, Generator
from functools import lru_cache
from types import CodeType, FrameType, MappingProxyType
from typing import Any, cast
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel
from RestrictedPython import compile_restricted, safe_builtins
from RestrictedPython.Eval import default_guarded_getitem, default_guarded_getiter
from RestrictedPython.Guards import (
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
)
from orcheo.nodes.registry import registry


LANGGRAPH_SCRIPT_FORMAT = "langgraph-script"

# Maximum UTF-8 encoded size for LangGraph scripts submitted through the importer.
DEFAULT_SCRIPT_SIZE_LIMIT = 128 * 1024  # 128 KiB

# Maximum wall-clock time spent executing a LangGraph script during ingestion.
DEFAULT_EXECUTION_TIMEOUT_SECONDS = 60.0

TraceFunc = Callable[[FrameType | None, str, object], object]

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

    builtin_snapshot = {name: value for name, value in safe_builtins.items()}
    builtin_snapshot.update(
        {
            "__build_class__": builtins.__build_class__,
            "__import__": _restricted_import,
            "property": property,
            "classmethod": classmethod,
            "staticmethod": staticmethod,
            "NotImplemented": NotImplemented,
            "Ellipsis": Ellipsis,
            "dict": dict,
            "list": list,
            "set": set,
        }
    )

    namespace: dict[str, Any] = {
        "__builtins__": MappingProxyType(builtin_snapshot),
        "__name__": "__orcheo_ingest__",
        "__package__": None,
        "_getattr_": getattr,
        "_getattr_static_": getattr,
        "_setattr_": setattr,
        "_getitem_": default_guarded_getitem,
        "_getiter_": default_guarded_getiter,
        "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
        "_unpack_sequence_": guarded_unpack_sequence,
        "_print_": print,
    }
    return namespace


class ScriptIngestionError(RuntimeError):
    """Raised when a LangGraph script cannot be converted into a workflow graph."""


def ingest_langgraph_script(
    source: str,
    *,
    entrypoint: str | None = None,
    max_script_bytes: int | None = DEFAULT_SCRIPT_SIZE_LIMIT,
    execution_timeout_seconds: float | None = DEFAULT_EXECUTION_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Return a workflow graph payload produced from a LangGraph Python script.

    The returned payload embeds the original script alongside a lightweight
    summary of the discovered LangGraph state graph. The summary is useful for
    visualisation and quick inspection while the original script is required to
    faithfully rebuild the graph during execution.
    """
    graph = load_graph_from_script(
        source,
        entrypoint=entrypoint,
        max_script_bytes=max_script_bytes,
        execution_timeout_seconds=execution_timeout_seconds,
    )
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
    max_script_bytes: int | None = DEFAULT_SCRIPT_SIZE_LIMIT,
    execution_timeout_seconds: float | None = DEFAULT_EXECUTION_TIMEOUT_SECONDS,
) -> StateGraph:
    """Execute a LangGraph Python script and return the discovered ``StateGraph``.

    Args:
        source: Python source code containing the LangGraph definition.
        entrypoint: Optional name of the variable or zero-argument callable that
            resolves to a ``StateGraph``. When omitted, the loader attempts to
            discover a single ``StateGraph`` instance defined in the module
            namespace.
        max_script_bytes: Maximum UTF-8 encoded size allowed for the script. Set
            to ``None`` to disable the limit.
        execution_timeout_seconds: Wall-clock timeout applied while executing the
            script. Set to ``None`` or a non-positive value to disable the
            timeout.

    Raises:
        ScriptIngestionError: if the script cannot be executed or no graph can
            be resolved from the resulting namespace.
    """
    _validate_script_size(source, max_script_bytes)

    namespace = _create_sandbox_namespace()

    try:
        compiled = _compile_langgraph_script(source)
        with _execution_timeout(execution_timeout_seconds):
            exec(compiled, namespace)
    except ScriptIngestionError:
        raise
    except TimeoutError as exc:
        # pragma: no cover - deterministic message asserted in tests
        message = "LangGraph script execution exceeded the configured timeout"
        raise ScriptIngestionError(message) from exc
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


@lru_cache(maxsize=128)
def _compile_langgraph_script(source: str) -> CodeType:
    """Compile a LangGraph script under RestrictedPython with caching."""
    return compile_restricted(source, "<langgraph-script>", "exec")


def _validate_script_size(source: str, max_script_bytes: int | None) -> None:
    """Raise ``ScriptIngestionError`` when the script exceeds the byte limit."""
    if max_script_bytes is None:
        return

    if max_script_bytes <= 0:
        msg = "LangGraph script size limit must be a positive integer"
        raise ScriptIngestionError(msg)

    encoded_length = len(source.encode("utf-8"))
    if encoded_length > max_script_bytes:
        msg = f"LangGraph script exceeds the permitted size of {max_script_bytes} bytes"
        raise ScriptIngestionError(msg)


@contextlib.contextmanager
def _execution_timeout(timeout_seconds: float | None) -> Generator[None, None, None]:
    """Enforce a wall-clock timeout around script execution."""
    if timeout_seconds is None or timeout_seconds <= 0:
        yield
        return

    use_signal = (
        hasattr(signal, "setitimer")
        and threading.current_thread() is threading.main_thread()
    )

    if use_signal:
        previous_handler = signal.getsignal(signal.SIGALRM)

        def _handle_timeout(_signum: int, _frame: FrameType | None) -> None:
            raise TimeoutError(
                "LangGraph script execution timed out"
            )  # pragma: no cover

        try:
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
            yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
        return

    deadline = time.perf_counter() + timeout_seconds

    def _trace_timeout(_frame: FrameType | None, event: str, _arg: object) -> TraceFunc:
        if event == "line" and time.perf_counter() > deadline:
            raise TimeoutError("LangGraph script execution timed out")
        return _trace_timeout

    previous_trace = cast(TraceFunc | None, sys.gettrace())
    previous_thread_trace = cast(TraceFunc | None, threading.gettrace())

    sys.settrace(cast(Any, _trace_timeout))
    threading.settrace(cast(Any, _trace_timeout))
    try:
        yield
    finally:
        if previous_trace is None:
            sys.settrace(cast(Any, None))
        else:
            sys.settrace(cast(Any, previous_trace))

        if previous_thread_trace is None:
            threading.settrace(cast(Any, None))
        else:
            threading.settrace(cast(Any, previous_thread_trace))


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
    "DEFAULT_EXECUTION_TIMEOUT_SECONDS",
    "DEFAULT_SCRIPT_SIZE_LIMIT",
    "LANGGRAPH_SCRIPT_FORMAT",
    "ScriptIngestionError",
    "ingest_langgraph_script",
    "load_graph_from_script",
]
