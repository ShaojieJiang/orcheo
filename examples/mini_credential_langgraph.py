"""Example LangGraph workflow demonstrating credential placeholders.

This example shows how to use credential placeholders in Orcheo workflows.
Credential placeholders use the [[credential_name]] syntax and are resolved
at runtime from the credential vault.
"""

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
                # Credential placeholder - resolved at runtime from vault
                "telegram_token": "[[telegram_bot]]",
                # Multiple credentials can be used
                "api_key": "[[openai_api_key]]",
                # You can also store static values alongside credentials
                "bot_name": "MyBot",
                "enabled": True,
            },
        ),
    )
    graph.add_edge(START, "store_secret")
    graph.add_edge("store_secret", END)
    return graph
