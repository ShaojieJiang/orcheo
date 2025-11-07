"""Integration-style tests for building full LangGraph graphs."""

from __future__ import annotations
import pytest
from orcheo.graph import builder


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

    assert graph is not None
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

    assert "actual_node" in graph.nodes
    assert "START" not in graph.nodes
    assert "END" not in graph.nodes
