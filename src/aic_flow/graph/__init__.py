"""Graph module for AIC Flow."""

from typing import Any
from langgraph.graph import END, START, StateGraph
from aic_flow.graph.state import State
from aic_flow.nodes.base import BaseNode
from aic_flow.nodes.registry import registry


def build_graph(graph_json: dict[str, Any]) -> StateGraph:
    """Build a graph from a JSON configuration."""
    graph = StateGraph(State)
    for node in graph_json["nodes"]:
        node_type = node["type"]
        match node_type:
            case "START" | "END":
                pass
            case _:
                node_class = registry.get_node(node_type)
                assert node_class
                node_params = {k: v for k, v in node.items() if k != "type"}
                node_instance: BaseNode = node_class(**node_params)
                graph.add_node(node["name"], node_instance)

    for source, target in graph_json["edges"]:
        graph.add_edge(
            source if source != "START" else START,
            target if target != "END" else END,
        )

    return graph
