"""Tests for LangGraph script ingestion helpers."""

from __future__ import annotations

import textwrap
from types import SimpleNamespace

import pytest

from orcheo.graph.builder import build_graph
from orcheo.graph.ingestion import (
    LANGGRAPH_SCRIPT_FORMAT,
    ScriptIngestionError,
    _serialise_branch,
    _resolve_graph,
    _unwrap_runnable,
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


def test_resolve_graph_with_unknown_object_returns_none() -> None:
    """Non-graph objects fall through the resolver."""

    assert _resolve_graph(object()) is None
