"""Tests covering edge node construction and conditional routing."""

from __future__ import annotations
import asyncio
from collections.abc import Mapping
from typing import Any
import pytest
from langgraph.graph import END, START
from langgraph.types import Send
from orcheo.graph import builder
from tests.graph._builder_test_helpers import DummyGraph, StubDecision


def test_build_edge_nodes_missing_name() -> None:
    """Edge node without name raises ValueError."""

    with pytest.raises(ValueError, match="Edge node must have a name"):
        builder._build_edge_nodes([{"type": "IfElseNode"}])


def test_build_edge_nodes_unknown_type() -> None:
    """Unknown edge node type raises ValueError."""

    with pytest.raises(ValueError, match="Unknown edge node type: missing"):
        builder._build_edge_nodes([{"name": "decision", "type": "missing"}])


def test_build_edge_nodes_success() -> None:
    """Successfully build edge node instances."""
    from orcheo.nodes.registry import registry

    edge_nodes_config = [
        {
            "name": "my_decision",
            "type": "IfElseNode",
            "condition": "{{check.value}}",
        }
    ]

    result = builder._build_edge_nodes(edge_nodes_config)

    assert "my_decision" in result
    assert result["my_decision"].name == "my_decision"
    node_class = registry.get_node("IfElseNode")
    assert isinstance(result["my_decision"], node_class)


@pytest.mark.parametrize(
    ("config", "expected_message"),
    [
        ({"path": "foo", "mapping": {"x": "END"}}, "source string"),
        ({"source": "A", "mapping": {"x": "END"}}, "path string"),
        ({"source": "A", "path": "foo"}, "non-empty mapping"),
    ],
)
def test_add_conditional_edges_validation(
    config: Mapping[str, Any], expected_message: str
) -> None:
    """Invalid conditional branch definitions raise detailed errors."""

    graph = DummyGraph()

    with pytest.raises(ValueError, match=expected_message):
        builder._add_conditional_edges(graph, config, {})


def test_add_conditional_edges_maps_vertices() -> None:
    """Conditional edges normalise mapping keys and defaults."""

    graph = DummyGraph()

    builder._add_conditional_edges(
        graph,
        {
            "source": "START",
            "path": "payload.flag",
            "mapping": {"true": "node_a", 0: "node_b"},
            "default": "END",
        },
        {},
    )

    assert graph.conditional_calls
    call = graph.conditional_calls[0]
    source, condition = call["args"][:2]
    assert source is START
    assert call["kwargs"] == {}
    assert condition({"payload": {"flag": True}}) == "node_a"
    assert condition({"payload": {"flag": 0}}) == "node_b"
    assert condition({"payload": {}}) is END


def test_add_conditional_edges_without_default_returns_end() -> None:
    """When no default is provided, unmatched conditions resolve to END."""

    graph = DummyGraph()

    builder._add_conditional_edges(
        graph,
        {
            "source": "START",
            "path": "payload.flag",
            "mapping": {"true": "node_a"},
        },
        {},
    )

    call = graph.conditional_calls[0]
    condition = call["args"][1]
    assert condition({"payload": {"flag": "unknown"}}) is END


def test_add_conditional_edges_preserves_default_for_edge_nodes() -> None:
    """Edge node conditional edges apply default routing when unmatched."""

    graph = DummyGraph()
    edge_node = StubDecision(["true", "unknown"])

    builder._add_conditional_edges(
        graph,
        {
            "source": "START",
            "path": "decision",
            "mapping": {"true": "END"},
            "default": "fallback",
        },
        {"decision": edge_node},
    )

    call = graph.conditional_calls[0]
    source, router = call["args"]
    assert source is START
    assert asyncio.run(router({}, {})) is END
    assert asyncio.run(router({}, {})) == "fallback"


def test_add_conditional_edges_normalises_default_edge_nodes() -> None:
    """Edge node defaults referencing sentinels are normalised before routing."""

    graph = DummyGraph()
    edge_node = StubDecision(["maybe"])

    builder._add_conditional_edges(
        graph,
        {
            "source": "START",
            "path": "decision",
            "mapping": {"true": "END"},
            "default": "END",
        },
        {"decision": edge_node},
    )

    router = graph.conditional_calls[0]["args"][1]
    assert asyncio.run(router({}, {})) is END


def test_add_conditional_edges_edge_node_without_default_routes_to_end() -> None:
    """Edge nodes without defaults fall back to END when unmatched."""

    graph = DummyGraph()
    edge_node = StubDecision(["unknown"])

    builder._add_conditional_edges(
        graph,
        {
            "source": "START",
            "path": "decision",
            "mapping": {"true": "next"},
        },
        {"decision": edge_node},
    )

    router = graph.conditional_calls[0]["args"][1]
    assert asyncio.run(router({}, {})) is END


def test_add_conditional_edges_edge_node_handles_sequence_results() -> None:
    """Edge node routers normalise sequence outputs including Send packets."""

    graph = DummyGraph()
    send_packet = Send("custom", {})
    edge_node = StubDecision([["true", send_packet]])

    builder._add_conditional_edges(
        graph,
        {
            "source": "START",
            "path": "decision",
            "mapping": {"true": "node_a"},
        },
        {"decision": edge_node},
    )

    router = graph.conditional_calls[0]["args"][1]
    destinations = asyncio.run(router({}, {}))
    assert destinations[0] == "node_a"
    assert destinations[1] is send_packet


def test_add_conditional_edges_without_edge_node() -> None:
    """Test conditional edges using state path (non-edge-node)."""

    graph = DummyGraph()

    builder._add_conditional_edges(
        graph,
        {
            "source": "node_a",
            "path": "state.decision",
            "mapping": {"option1": "node_b", "option2": "node_c"},
        },
        {},
    )

    assert len(graph.conditional_calls) == 1
    call = graph.conditional_calls[0]
    source, condition = call["args"][:2]
    assert source == "node_a"
    assert callable(condition)
