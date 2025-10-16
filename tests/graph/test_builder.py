"""Tests for the graph builder utilities."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any
import pytest
from langgraph.graph import END, START
from orcheo.graph import builder


class _DummyGraph:
    """Minimal graph stub recording interactions."""

    def __init__(self) -> None:
        self.edges: list[tuple[Any, Any]] = []
        self.conditional_calls: list[tuple[Any, Any]] = []

    def add_edge(self, source: Any, target: Any) -> None:
        self.edges.append((source, target))

    def add_conditional_edges(self, source: Any, condition: Any) -> None:
        self.conditional_calls.append((source, condition))


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
        builder._add_conditional_edges(graph, config)


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
    )

    assert graph.conditional_calls, "conditional edges should be registered"
    source, condition = graph.conditional_calls[0]
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
    )

    _, condition = graph.conditional_calls[0]
    assert condition({"payload": {"flag": "unknown"}}) is END


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
