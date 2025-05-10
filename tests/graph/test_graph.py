from langgraph.graph import END, START, StateGraph
from aic_flow.graph import build_graph
from aic_flow.graph.state import State
from aic_flow.nodes.code import PythonCodeNode


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
    graph.add_node("code", PythonCodeNode(name="code", code="print('Hello, world!')"))
    graph.add_edge(START, "code")
    graph.add_edge("code", END)
    return graph.compile()


def test_build_graph():
    graph = build_graph(graph_config).compile()
    reference_graph = build_lang_graph()
    assert (
        graph.get_graph().draw_mermaid() == reference_graph.get_graph().draw_mermaid()
    )
