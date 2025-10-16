"""Simple LangGraph workflow demonstrating state access in Orcheo.

When using LangGraph scripts with Orcheo, you have full control over the
state definition. The backend passes your input parameters directly to the
graph without adding any predefined fields.

Key features:
- Use plain dict for state (StateGraph(dict))
- Access inputs directly: state.get("param_name")
- Define any custom state fields you need
- No predefined "messages" or "results" fields
- RestrictedPython limitations apply (no variables starting with "_")
"""

from langgraph.graph import StateGraph


def greet_user(state):
    """Generate a greeting message based on the name in state."""
    name = state.get("name", "there")
    return {"greeting": f"Hello {name}!"}


def format_message(state):
    """Convert greeting message to uppercase."""
    greeting = state.get("greeting", "")
    return {"shout": greeting.upper()}


def build_graph():
    """Build and return the LangGraph workflow."""
    graph = StateGraph(dict)
    graph.add_node("greet_user", greet_user)
    graph.add_node("format_message", format_message)
    graph.add_edge("greet_user", "format_message")
    graph.set_entry_point("greet_user")
    graph.set_finish_point("format_message")
    return graph


if __name__ == "__main__":
    graph = build_graph().compile()
    result = graph.invoke({"name": "John"})
    print(result)
    print(result["shout"])
