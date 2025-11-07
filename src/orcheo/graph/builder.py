"""Graph builder module for Orcheo."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from langgraph.graph import StateGraph
from orcheo.graph.conditional import add_conditional_edges
from orcheo.graph.edge_nodes import build_edge_nodes
from orcheo.graph.ingestion import LANGGRAPH_SCRIPT_FORMAT, load_graph_from_script
from orcheo.graph.normalization import normalise_edges, normalise_vertex
from orcheo.graph.parallel import add_parallel_branches
from orcheo.graph.state import State
from orcheo.nodes.registry import registry


def build_graph(graph_json: Mapping[str, Any]) -> StateGraph:
    """Build a LangGraph graph from a configuration payload."""
    if graph_json.get("format") == LANGGRAPH_SCRIPT_FORMAT:
        source = graph_json.get("source")
        if not isinstance(source, str) or not source.strip():
            msg = "Script graph configuration requires a non-empty source"
            raise ValueError(msg)
        entrypoint_value = graph_json.get("entrypoint")
        if entrypoint_value is not None and not isinstance(entrypoint_value, str):
            msg = "Entrypoint must be a string when provided"
            raise ValueError(msg)
        return load_graph_from_script(source, entrypoint=entrypoint_value)

    graph = StateGraph(State)
    nodes = list(graph_json.get("nodes", []))
    edges = list(graph_json.get("edges", []))
    edge_nodes = list(graph_json.get("edge_nodes", []))

    edge_node_instances = build_edge_nodes(edge_nodes)

    for node in nodes:
        node_type = node.get("type")
        if node_type in {"START", "END"}:
            continue
        node_class = registry.get_node(str(node_type))
        if node_class is None:
            msg = f"Unknown node type: {node_type}"
            raise ValueError(msg)
        node_params = {k: v for k, v in node.items() if k != "type"}
        node_instance = node_class(**node_params)
        graph.add_node(str(node["name"]), node_instance)

    for source, target in normalise_edges(edges):
        graph.add_edge(normalise_vertex(source), normalise_vertex(target))

    for branch in graph_json.get("conditional_edges", []):
        add_conditional_edges(graph, branch, edge_node_instances)

    for parallel in graph_json.get("parallel_branches", []):
        add_parallel_branches(graph, parallel)

    return graph
