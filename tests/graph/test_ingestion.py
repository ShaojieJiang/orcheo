"""Tests for LangGraph script ingestion helpers."""

from __future__ import annotations

import textwrap

import pytest

from orcheo.graph.builder import build_graph
from orcheo.graph.ingestion import (
    LANGGRAPH_SCRIPT_FORMAT,
    ScriptIngestionError,
    ingest_langgraph_script,
)


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
