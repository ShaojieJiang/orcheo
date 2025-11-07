"""Load LangGraph StateGraph instances from Python scripts."""

from __future__ import annotations
import inspect
from typing import Any
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from orcheo.graph.ingestion.config import (
    DEFAULT_EXECUTION_TIMEOUT_SECONDS,
    DEFAULT_SCRIPT_SIZE_LIMIT,
)
from orcheo.graph.ingestion.exceptions import ScriptIngestionError
from orcheo.graph.ingestion.sandbox import (
    compile_langgraph_script,
    create_sandbox_namespace,
    execution_timeout,
    validate_script_size,
)


def load_graph_from_script(
    source: str,
    *,
    entrypoint: str | None = None,
    max_script_bytes: int | None = DEFAULT_SCRIPT_SIZE_LIMIT,
    execution_timeout_seconds: float | None = DEFAULT_EXECUTION_TIMEOUT_SECONDS,
) -> StateGraph:
    """Execute a LangGraph Python script and return the discovered ``StateGraph``."""
    validate_script_size(source, max_script_bytes)
    namespace = create_sandbox_namespace()

    try:
        compiled = compile_langgraph_script(source)
        with execution_timeout(execution_timeout_seconds):
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


__all__ = ["load_graph_from_script"]
