"""Example LangGraph workflow demonstrating credential placeholders."""

from langgraph.graph import END, START, StateGraph

from orcheo.graph.state import State
from orcheo.nodes.logic import SetVariableNode


def build_graph() -> StateGraph:
    """Return a LangGraph with a credential placeholder."""

    graph = StateGraph(State)
    graph.add_node(
        "store_secret",
        SetVariableNode(
            name="store_secret",
            variables={
                "token": "[[telegram_bot]]",
                "echo": "{{inputs.message}}",
            },
        ),
    )
    graph.add_edge(START, "store_secret")
    graph.add_edge("store_secret", END)
    return graph


graph = build_graph()
"""Expose ``graph`` for LangGraph ingestion."""
