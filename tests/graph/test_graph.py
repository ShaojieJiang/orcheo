from langgraph.graph import END, START, StateGraph
from orcheo.graph.builder import build_graph
from orcheo.graph.state import State
from orcheo.nodes.code import PythonCode


graph_config = {
    "nodes": [
        {"name": "START", "type": "START"},
        {"name": "code", "type": "PythonCode", "code": "print('Hello, world!')"},
        {"name": "END", "type": "END"},
    ],
    "edges": [("START", "code"), ("code", "END")],
}


def build_lang_graph():
    """Build a reference graph for testing."""
    graph = StateGraph(State)
    graph.add_node("code", PythonCode(name="code", code="print('Hello, world!')"))
    graph.add_edge(START, "code")
    graph.add_edge("code", END)
    return graph.compile()


def test_build_graph():
    graph = build_graph(graph_config).compile()
    reference_graph = build_lang_graph()
    assert (
        graph.get_graph().draw_mermaid() == reference_graph.get_graph().draw_mermaid()
    )
