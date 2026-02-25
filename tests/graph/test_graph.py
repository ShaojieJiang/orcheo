from langgraph.graph import END, START, StateGraph
from orcheo.graph.builder import build_graph
from orcheo.graph.state import State
from orcheo.nodes.logic import SetVariableNode


graph_config = {
    "nodes": [
        {"name": "START", "type": "START"},
        {"name": "code", "type": "SetVariableNode", "variables": {"message": "hello"}},
        {"name": "END", "type": "END"},
    ],
    "edges": [("START", "code"), ("code", "END")],
}


def build_lang_graph():
    """Build a reference graph for testing."""
    graph = StateGraph(State)
    graph.add_node("code", SetVariableNode(name="code", variables={"message": "hello"}))
    graph.add_edge(START, "code")
    graph.add_edge("code", END)
    return graph.compile()


def test_build_graph():
    graph = build_graph(graph_config).compile()
    reference_graph = build_lang_graph()
    assert (
        graph.get_graph().draw_mermaid() == reference_graph.get_graph().draw_mermaid()
    )


def test_build_graph_supports_branching_parallel_and_loops():
    config = {
        "nodes": [
            {"name": "START", "type": "START"},
            {
                "name": "router",
                "type": "SetVariableNode",
                "variables": {"route": "left"},
            },
            {
                "name": "fanout",
                "type": "SetVariableNode",
                "variables": {"fanout": True},
            },
            {
                "name": "left_worker",
                "type": "SetVariableNode",
                "variables": {"result": "left"},
            },
            {
                "name": "right_worker",
                "type": "SetVariableNode",
                "variables": {"result": "right"},
            },
            {
                "name": "joiner",
                "type": "SetVariableNode",
                "variables": {"joined": True},
            },
            {"name": "END", "type": "END"},
        ],
        "edges": [
            ("START", "router"),
            ("router", "fanout"),
            ("joiner", "END"),
        ],
        "conditional_edges": [
            {
                "source": "router",
                "path": "outputs.router.route",
                "mapping": {
                    "left": "left_worker",
                    "right": "right_worker",
                    "repeat": "router",
                },
                "default": "joiner",
            }
        ],
        "parallel_branches": [
            {
                "source": "fanout",
                "targets": ["left_worker", "right_worker"],
                "join": "joiner",
            }
        ],
    }

    graph = build_graph(config).compile()
    edges = {(edge.source, edge.target) for edge in graph.get_graph().edges}
    assert ("fanout", "left_worker") in edges
    assert ("fanout", "right_worker") in edges
    assert ("left_worker", "joiner") in edges
    assert ("right_worker", "joiner") in edges

    trigger_map = graph.trigger_to_nodes
    assert trigger_map["branch:to:left_worker"] == ["left_worker"]
    assert trigger_map["branch:to:right_worker"] == ["right_worker"]
    assert trigger_map["branch:to:router"] == ["router"]  # loop support
    assert trigger_map["branch:to:joiner"] == ["joiner"]
