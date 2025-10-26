"""Tests for the graph builder utilities."""

from __future__ import annotations
import asyncio
from collections.abc import Mapping
from typing import Any

import pytest
from langgraph.graph import END, START
from langgraph.types import Send

from orcheo.graph import builder


class _DummyGraph:
    """Minimal graph stub recording interactions."""

    def __init__(self) -> None:
        self.edges: list[tuple[Any, Any]] = []
        self.conditional_calls: list[dict[str, Any]] = []

    def add_edge(self, source: Any, target: Any) -> None:
        self.edges.append((source, target))

    def add_conditional_edges(self, *args: Any, **kwargs: Any) -> None:
        self.conditional_calls.append({"args": args, "kwargs": kwargs})


class _StubDecision:
    """Simple async decision node that yields predetermined outcomes."""

    def __init__(self, outcomes: list[Any]) -> None:
        self._outcomes = list(outcomes)

    async def __call__(self, state: Any, config: Any) -> Any:
        return self._outcomes.pop(0)


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

    # Use a real registered edge node type
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
    # Verify it's the correct node class
    node_class = registry.get_node("IfElseNode")
    assert isinstance(result["my_decision"], node_class)


def test_build_graph_unknown_node_type() -> None:
    """Unknown node types produce a clear ValueError."""

    with pytest.raises(ValueError, match="Unknown node type: missing"):
        builder.build_graph({"nodes": [{"name": "foo", "type": "missing"}]})


def test_build_graph_script_format_empty_source() -> None:
    """Script format with empty source raises ValueError."""

    with pytest.raises(ValueError, match="non-empty source"):
        builder.build_graph({"format": "langgraph-script", "source": ""})

    with pytest.raises(ValueError, match="non-empty source"):
        builder.build_graph({"format": "langgraph-script", "source": "   "})


def test_build_graph_script_format_invalid_entrypoint_type() -> None:
    """Script format with non-string entrypoint raises ValueError."""

    with pytest.raises(ValueError, match="Entrypoint must be a string"):
        builder.build_graph(
            {"format": "langgraph-script", "source": "valid_code", "entrypoint": 123}
        )


def test_normalise_edges_validation() -> None:
    """Edge normalisation rejects malformed entries."""

    with pytest.raises(ValueError, match="Invalid edge entry"):
        builder._normalise_edges([object()])  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Edge endpoints must be strings"):
        builder._normalise_edges([("start", 1)])  # type: ignore[arg-type]


def test_normalise_edges_supports_mapping_entries() -> None:
    """Mapping-style edge definitions are normalised correctly."""

    result = builder._normalise_edges([{"source": "A", "target": "B"}])
    assert result == [("A", "B")]


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

    graph = _DummyGraph()

    with pytest.raises(ValueError, match=expected_message):
        builder._add_conditional_edges(graph, config, {})


def test_add_conditional_edges_maps_vertices() -> None:
    """Conditional edges normalise mapping keys and defaults."""

    graph = _DummyGraph()

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

    assert graph.conditional_calls, "conditional edges should be registered"
    call = graph.conditional_calls[0]
    source, condition = call["args"][:2]
    assert call["kwargs"] == {}
    assert source is START
    assert condition({"payload": {"flag": True}}) == "node_a"
    assert condition({"payload": {"flag": 0}}) == "node_b"
    assert condition({"payload": {}}) is END


def test_add_conditional_edges_without_default_returns_end() -> None:
    """When no default is provided, unmatched conditions resolve to END."""

    graph = _DummyGraph()

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

    graph = _DummyGraph()
    edge_node = _StubDecision(["true", "unknown"])

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
    assert call["kwargs"] == {}


def test_add_conditional_edges_normalises_default_edge_nodes() -> None:
    """Edge node defaults referencing sentinels are normalised before routing."""

    graph = _DummyGraph()
    edge_node = _StubDecision(["maybe"])

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

    graph = _DummyGraph()
    edge_node = _StubDecision(["unknown"])

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

    graph = _DummyGraph()
    send_packet = Send("custom", {})
    edge_node = _StubDecision([["true", send_packet]])

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


@pytest.mark.parametrize(
    ("config", "expected_message"),
    [
        ({"targets": ["A"]}, "source string"),
        ({"source": "START", "targets": "A"}, "list of targets"),
        (
            {"source": "START", "targets": ["A", 1]},
            "targets must be strings",
        ),
        ({"source": "START", "targets": []}, "targets must be strings"),
    ],
)
def test_add_parallel_branches_validation(
    config: Mapping[str, Any], expected_message: str
) -> None:
    """Parallel branch validation surfaces precise errors."""

    graph = _DummyGraph()

    with pytest.raises(ValueError, match=expected_message):
        builder._add_parallel_branches(graph, config)


def test_add_parallel_branches_with_join() -> None:
    """Parallel branches normalise endpoints and add join edges."""

    graph = _DummyGraph()

    builder._add_parallel_branches(
        graph,
        {"source": "START", "targets": ["A", "END"], "join": "END"},
    )

    assert graph.edges[:2] == [(START, "A"), (START, END)]
    # Join edges should point each branch to END
    assert graph.edges[2:] == [("A", END), (END, END)]


def test_add_parallel_branches_without_join() -> None:
    """Parallel branches may omit a join target."""

    graph = _DummyGraph()

    builder._add_parallel_branches(
        graph,
        {"source": "A", "targets": ["B", "C"]},
    )

    assert graph.edges == [("A", "B"), ("A", "C")]


def test_make_condition_falls_back_to_default_and_end() -> None:
    """The generated resolver handles nulls, defaults and missing paths."""

    mapping = {"true": "pos", "false": "neg", "value": "other"}
    condition = builder._make_condition(
        "payload.result",
        mapping,
        default_target="fallback",
    )

    assert condition({"payload": {"result": True}}) == "pos"
    assert condition({"payload": {"result": False}}) == "neg"
    assert condition({"payload": {"result": "value"}}) == "other"
    assert condition({"payload": {"result": None}}) == "fallback"
    assert condition({"payload": {}}) == "fallback"
    assert condition({"payload": 7}) == "fallback"

    no_default = builder._make_condition("payload.value", {}, default_target=None)
    assert no_default({"payload": {"value": 123}}) is END


def test_build_graph_with_edge_nodes_integration() -> None:
    """Integration test for building a graph with edge nodes (decision nodes)."""

    graph_config = {
        "nodes": [
            {"name": "start_node", "type": "PythonCode", "code": "return {'value': 1}"},
            {
                "name": "true_branch",
                "type": "PythonCode",
                "code": "return {'result': 'yes'}",
            },
            {
                "name": "false_branch",
                "type": "PythonCode",
                "code": "return {'result': 'no'}",
            },
        ],
        "edge_nodes": [
            {
                "name": "decision",
                "type": "IfElseNode",
                "condition": "{{start_node.value}}",
            }
        ],
        "edges": [{"source": "START", "target": "start_node"}],
        "conditional_edges": [
            {
                "source": "start_node",
                "path": "decision",
                "mapping": {"true": "true_branch", "false": "false_branch"},
                "default": "false_branch",
            }
        ],
    }

    graph = builder.build_graph(graph_config)

    # Verify graph was built successfully
    assert graph is not None
    # Verify nodes were added
    assert "start_node" in graph.nodes
    assert "true_branch" in graph.nodes
    assert "false_branch" in graph.nodes


def test_build_graph_with_regular_nodes_and_edges() -> None:
    """Test building a graph with regular nodes and edges."""

    graph_config = {
        "nodes": [
            {"name": "node_a", "type": "PythonCode", "code": "return {'x': 1}"},
            {"name": "node_b", "type": "PythonCode", "code": "return {'y': 2}"},
            {"name": "node_c", "type": "PythonCode", "code": "return {'z': 3}"},
        ],
        "edges": [
            {"source": "START", "target": "node_a"},
            {"source": "node_a", "target": "node_b"},
            {"source": "node_b", "target": "node_c"},
            {"source": "node_c", "target": "END"},
        ],
    }

    graph = builder.build_graph(graph_config)

    assert graph is not None
    assert "node_a" in graph.nodes
    assert "node_b" in graph.nodes
    assert "node_c" in graph.nodes


def test_build_graph_skips_start_and_end_nodes() -> None:
    """Test that START and END node types are properly skipped."""

    graph_config = {
        "nodes": [
            {"name": "START", "type": "START"},
            {"name": "actual_node", "type": "PythonCode", "code": "return {}"},
            {"name": "END", "type": "END"},
        ],
        "edges": [
            {"source": "START", "target": "actual_node"},
            {"source": "actual_node", "target": "END"},
        ],
    }

    graph = builder.build_graph(graph_config)

    # Should only have the actual_node, not START or END
    assert "actual_node" in graph.nodes
    assert "START" not in graph.nodes
    assert "END" not in graph.nodes


def test_make_condition_null_key_handling() -> None:
    """Test that null values are mapped to 'null' key in condition mapping."""

    mapping = {"null": "null_handler", "value": "value_handler"}
    condition = builder._make_condition("data.field", mapping, default_target=None)

    # None should map to "null" key
    assert condition({"data": {"field": None}}) == "null_handler"


def test_normalise_vertex() -> None:
    """Test vertex normalisation for START and END sentinels."""

    assert builder._normalise_vertex("START") is START
    assert builder._normalise_vertex("END") is END
    assert builder._normalise_vertex("regular_node") == "regular_node"


def test_add_conditional_edges_without_edge_node() -> None:
    """Test conditional edges using state path (non-edge-node)."""

    graph = _DummyGraph()

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
    # Verify the condition is callable
    assert callable(condition)
