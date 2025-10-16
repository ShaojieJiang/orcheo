"""Tests for LangGraph script ingestion helpers."""

from __future__ import annotations
import itertools
import textwrap
from types import SimpleNamespace
import pytest
from orcheo.graph.builder import build_graph
from orcheo.graph.ingestion import (
    DEFAULT_SCRIPT_SIZE_LIMIT,
    LANGGRAPH_SCRIPT_FORMAT,
    ScriptIngestionError,
    _compile_langgraph_script,
    _execution_timeout,
    _resolve_graph,
    _serialise_branch,
    _unwrap_runnable,
    _validate_script_size,
    ingest_langgraph_script,
)
from orcheo.nodes.rss import RSSNode


def test_ingest_script_with_entrypoint() -> None:
    """Scripts with an explicit entrypoint are converted into graph payloads."""

    script = textwrap.dedent(
        """
        from langgraph.graph import StateGraph
        from orcheo.graph.state import State
        from orcheo.nodes.rss import RSSNode

        def build_graph():
            graph = StateGraph(State)
            graph.add_node("rss", RSSNode(name="rss", sources=["https://example.com/feed"]))
            graph.set_entry_point("rss")
            graph.set_finish_point("rss")
            return graph
        """
    )

    payload = ingest_langgraph_script(script, entrypoint="build_graph")

    assert payload["format"] == LANGGRAPH_SCRIPT_FORMAT
    assert (
        payload["source"].strip().startswith("from langgraph.graph import StateGraph")
    )
    assert payload["entrypoint"] == "build_graph"
    summary = payload["summary"]
    assert summary["edges"] == [("START", "rss"), ("rss", "END")]
    assert summary["nodes"][0]["type"] == "RSSNode"

    graph = build_graph(payload)
    assert set(graph.nodes.keys()) == {"rss"}


def test_ingest_script_without_entrypoint_auto_discovers_graph() -> None:
    """Scripts defining a single graph variable are auto-discovered."""

    script = textwrap.dedent(
        """
        from langgraph.graph import StateGraph
        from orcheo.graph.state import State

        graph = StateGraph(State)
        graph.add_node("first", lambda state: state)
        graph.set_entry_point("first")
        graph.set_finish_point("first")
        """
    )

    payload = ingest_langgraph_script(script)

    assert payload["entrypoint"] is None
    summary = payload["summary"]
    assert summary["edges"] == [("START", "first"), ("first", "END")]


def test_ingest_script_with_multiple_candidates_requires_entrypoint() -> None:
    """Multiple graphs require an explicit entrypoint to disambiguate."""

    script = textwrap.dedent(
        """
        from langgraph.graph import StateGraph
        from orcheo.graph.state import State

        first = StateGraph(State)
        second = StateGraph(State)
        """
    )

    with pytest.raises(ScriptIngestionError):
        ingest_langgraph_script(script)


def test_ingest_script_rejects_forbidden_imports() -> None:
    """Scripts attempting to import forbidden modules are rejected."""

    script = textwrap.dedent(
        """
        import os
        from langgraph.graph import StateGraph
        from orcheo.graph.state import State

        graph = StateGraph(State)
        graph.set_entry_point("first")
        graph.set_finish_point("first")
        """
    )

    with pytest.raises(ScriptIngestionError):
        ingest_langgraph_script(script)


def test_ingest_script_rejects_relative_imports() -> None:
    """Relative imports are blocked by the sandbox import hook."""

    script = textwrap.dedent(
        """
        from .foo import bar
        """
    )

    with pytest.raises(ScriptIngestionError):
        ingest_langgraph_script(script)


def test_ingest_script_missing_entrypoint_errors() -> None:
    """Referencing an entrypoint that does not exist raises an error."""

    script = textwrap.dedent(
        """
        from langgraph.graph import StateGraph
        from orcheo.graph.state import State

        graph = StateGraph(State)
        graph.set_entry_point("first")
        graph.set_finish_point("first")
        """
    )

    with pytest.raises(ScriptIngestionError):
        ingest_langgraph_script(script, entrypoint="missing")


def test_ingest_script_without_candidates_errors() -> None:
    """Scripts that fail to define a graph raise a conversion error."""

    script = """value = 42"""

    with pytest.raises(ScriptIngestionError):
        ingest_langgraph_script(script)


def test_ingest_script_entrypoint_requires_arguments() -> None:
    """Entrypoints requiring arguments are rejected."""

    script = textwrap.dedent(
        """
        from langgraph.graph import StateGraph
        from orcheo.graph.state import State

        def build_graph(name: str):
            graph = StateGraph(State)
            graph.set_entry_point("first")
            graph.set_finish_point("first")
            return graph
        """
    )

    with pytest.raises(ScriptIngestionError):
        ingest_langgraph_script(script, entrypoint="build_graph")


def test_ingest_script_handles_compiled_graph_entrypoint() -> None:
    """Compiled graphs referenced as entrypoints are resolved to builders."""

    script = textwrap.dedent(
        """
        from langgraph.graph import StateGraph
        from orcheo.graph.state import State

        graph = StateGraph(State)
        graph.add_node("first", lambda state: state)
        graph.set_entry_point("first")
        graph.set_finish_point("first")
        compiled = graph.compile()
        """
    )

    payload = ingest_langgraph_script(script, entrypoint="compiled")

    summary = payload["summary"]
    assert summary["edges"] == [("START", "first"), ("first", "END")]


def test_ingest_script_entrypoint_not_resolvable() -> None:
    """Entrypoints referencing non-graph objects raise an error."""

    script = textwrap.dedent(
        """
        class Dummy:
            pass

        candidate = Dummy()
        """
    )

    with pytest.raises(ScriptIngestionError):
        ingest_langgraph_script(script, entrypoint="candidate")


def test_unwrap_runnable_prefers_wrapped_func() -> None:
    """Wrappers exposing ``func`` with a BaseModel are unwrapped."""

    node = RSSNode(name="rss", sources=["https://example.com/feed"])
    wrapper = SimpleNamespace(func=node)

    assert _unwrap_runnable(wrapper) is node


def test_serialise_branch_with_mapping_and_default() -> None:
    """Branch metadata includes mapping, default target, and callable names."""

    branch = SimpleNamespace(
        ends={"success": "__start__", "failure": "__end__"},
        then="__end__",
        path=SimpleNamespace(func=lambda: None),
    )

    payload = _serialise_branch("node", "result", branch)

    assert payload["mapping"] == {"success": "START", "failure": "END"}
    assert payload["default"] == "END"
    assert payload["callable"] == "<lambda>"


def test_serialise_branch_without_optional_fields() -> None:
    """Branches without mapping or callables only expose core metadata."""

    branch = SimpleNamespace(ends=None, then=None)

    payload = _serialise_branch("node", "result", branch)

    assert payload == {"source": "node", "branch": "result"}


def test_ingest_script_exceeding_size_limit() -> None:
    """Scripts larger than the configured limit are rejected."""

    oversized = "a" * (DEFAULT_SCRIPT_SIZE_LIMIT + 1)

    with pytest.raises(ScriptIngestionError, match="exceeds the permitted size"):
        ingest_langgraph_script(oversized)


def test_validate_script_size_without_limit() -> None:
    """Unbounded scripts are accepted without validation errors."""

    assert _validate_script_size("payload", None) is None


def test_validate_script_size_rejects_non_positive_limits() -> None:
    """Non-positive script size limits are rejected."""

    with pytest.raises(ScriptIngestionError, match="must be a positive integer"):
        _validate_script_size("payload", 0)


def test_ingest_script_enforces_execution_timeout() -> None:
    """Infinite loops trigger a timeout during script execution."""

    script = "while True:\n    pass\n"

    with pytest.raises(
        ScriptIngestionError, match="execution exceeded the configured timeout"
    ):
        ingest_langgraph_script(script, execution_timeout_seconds=0.1)


def test_compile_langgraph_script_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """Repeated ingestion of the same script reuses the cached bytecode."""

    script = textwrap.dedent(
        """
        from langgraph.graph import StateGraph
        from orcheo.graph.state import State

        graph = StateGraph(State)
        graph.set_entry_point("first")
        graph.set_finish_point("first")
        """
    )

    call_count = 0

    def _fake_compile(source: str, filename: str, mode: str):
        nonlocal call_count
        call_count += 1
        return compile(source, filename, mode)

    _compile_langgraph_script.cache_clear()
    monkeypatch.setattr("orcheo.graph.ingestion.compile_restricted", _fake_compile)

    try:
        ingest_langgraph_script(script)
        ingest_langgraph_script(script)
    finally:
        _compile_langgraph_script.cache_clear()

    assert call_count == 1


def test_execution_timeout_disabled_for_non_positive_values() -> None:
    """Zero or negative timeouts disable deadline enforcement."""

    with _execution_timeout(0):
        assert True


def test_execution_timeout_trace_fallback_enforces_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trace-based timeout enforcement raises when signals are unavailable."""

    class FakeSys:
        def __init__(self) -> None:
            self._trace: object | None = None
            self.calls: list[object | None] = []

        def gettrace(self) -> object | None:
            return self._trace

        def settrace(self, trace: object | None) -> None:
            self.calls.append(trace)
            self._trace = trace

    class FakeThreading:
        def __init__(self) -> None:
            self._trace: object | None = None
            self._current_thread = object()
            self._main_thread = object()
            self.calls: list[object | None] = []

        def current_thread(self) -> object:
            return self._current_thread

        def main_thread(self) -> object:
            return self._main_thread

        def gettrace(self) -> object | None:
            return self._trace

        def settrace(self, trace: object | None) -> None:
            self.calls.append(trace)
            self._trace = trace

    fake_sys = FakeSys()
    fake_threading = FakeThreading()
    monkeypatch.setattr("orcheo.graph.ingestion.sys", fake_sys)
    monkeypatch.setattr("orcheo.graph.ingestion.threading", fake_threading)

    perf_counter_values = itertools.chain([0.0, 0.2], itertools.repeat(0.2))
    monkeypatch.setattr(
        "orcheo.graph.ingestion.time.perf_counter",
        lambda: next(perf_counter_values),
    )

    original_trace = fake_sys.gettrace()
    original_thread_trace = fake_threading.gettrace()

    with pytest.raises(TimeoutError):
        with _execution_timeout(0.1):
            trace = fake_sys.gettrace()
            assert callable(trace)
            next_trace = trace(None, "call", None)
            assert next_trace is trace
            next_trace(None, "line", None)

    assert fake_sys.gettrace() is original_trace
    assert fake_threading.gettrace() is original_thread_trace
    assert fake_sys.calls[-1] is None
    assert fake_threading.calls[-1] is None


def test_execution_timeout_restores_existing_traces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Existing trace functions are restored after the context exits."""

    class FakeSys:
        def __init__(self) -> None:
            self._trace: object | None = object()
            self.calls: list[object | None] = []

        def gettrace(self) -> object | None:
            return self._trace

        def settrace(self, trace: object | None) -> None:
            self.calls.append(trace)
            self._trace = trace

    class FakeThreading:
        def __init__(self) -> None:
            self._trace: object | None = object()
            self._current_thread = object()
            self._main_thread = object()
            self.calls: list[object | None] = []

        def current_thread(self) -> object:
            return self._current_thread

        def main_thread(self) -> object:
            return self._main_thread

        def gettrace(self) -> object | None:
            return self._trace

        def settrace(self, trace: object | None) -> None:
            self.calls.append(trace)
            self._trace = trace

    fake_sys = FakeSys()
    fake_threading = FakeThreading()
    monkeypatch.setattr("orcheo.graph.ingestion.sys", fake_sys)
    monkeypatch.setattr("orcheo.graph.ingestion.threading", fake_threading)

    monkeypatch.setattr(
        "orcheo.graph.ingestion.time.perf_counter",
        lambda: 0.0,
    )

    original_trace = fake_sys.gettrace()
    original_thread_trace = fake_threading.gettrace()

    with _execution_timeout(0.1):
        trace = fake_sys.gettrace()
        assert callable(trace)
        returned = trace(None, "call", None)
        assert returned is trace

    assert fake_sys.gettrace() is original_trace
    assert fake_threading.gettrace() is original_thread_trace
    assert fake_sys.calls[-1] is original_trace
    assert fake_threading.calls[-1] is original_thread_trace


def test_resolve_graph_with_unknown_object_returns_none() -> None:
    """Non-graph objects fall through the resolver."""

    assert _resolve_graph(object()) is None
