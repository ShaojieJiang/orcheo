"""Load LangGraph StateGraph instances from Python scripts."""

from __future__ import annotations
import asyncio
import inspect
from collections.abc import Awaitable
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


def _format_syntax_error_message(exc: SyntaxError) -> str:
    """Format a SyntaxError into a user-friendly message."""
    if exc.args and isinstance(exc.args[0], str):
        # Format: "Line 39: AnnAssign statements are not allowed."
        # or tuple with multiple error messages
        if isinstance(exc.args[0], str) and exc.args[0].startswith("Line"):
            return f"Compilation error: {exc.args[0]}"
        # Handle tuple of errors
        error_messages = ", ".join(str(arg) for arg in exc.args if isinstance(arg, str))
        return f"Compilation error: {error_messages}"
    return f"Compilation error: {exc}"


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
    except SyntaxError as exc:
        # RestrictedPython syntax errors come with detailed information
        message = _format_syntax_error_message(exc)
        raise ScriptIngestionError(message) from exc
    except TimeoutError as exc:
        # pragma: no cover - deterministic message asserted in tests
        message = "LangGraph script execution exceeded the configured timeout"
        raise ScriptIngestionError(message) from exc
    except Exception as exc:  # pragma: no cover - exercised via tests
        message = f"Runtime error during script execution: {type(exc).__name__}: {exc}"
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


async def _await_awaitable(awaitable: Awaitable[Any]) -> Any:
    """Await ``awaitable`` within a coroutine context."""
    return await awaitable


def _resolve_graph(obj: Any) -> StateGraph | None:
    """Return a ``StateGraph`` from the supplied object if possible."""
    resolved: StateGraph | None = None

    if isinstance(obj, StateGraph):
        resolved = obj
    elif isinstance(obj, CompiledStateGraph):
        resolved = obj.builder
    elif inspect.isawaitable(obj):
        result: Any
        try:
            result = asyncio.run(_await_awaitable(obj))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(_await_awaitable(obj))
            finally:
                loop.close()
        resolved = _resolve_graph(result)
    elif callable(obj):
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
        resolved = _resolve_graph(result)

    return resolved


__all__ = ["load_graph_from_script"]
