"""Example demonstrating full control over state definition in LangGraph scripts.

This script shows how developers can define their own state structure with
custom fields and reducers when using LangGraph scripts with Orcheo.
"""

from langgraph.graph import StateGraph


def step1(state):
    """First step: initialize counter and add a message."""
    counter = state.get("counter", 0)
    messages = state.get("messages", [])
    return {
        "counter": counter + 1,
        "messages": messages + ["Step 1 executed"],
        "step1_output": "Data from step 1",
    }


def step2(state):
    """Second step: increment counter and add another message."""
    counter = state.get("counter", 0)
    messages = state.get("messages", [])
    step1_data = state.get("step1_output", "")
    return {
        "counter": counter + 1,
        "messages": messages + ["Step 2 executed"],
        "final_result": f"Processed: {step1_data}",
    }


def build_graph():
    """Build and return the LangGraph workflow with custom state."""
    # Using dict state gives full control - no predefined fields
    graph = StateGraph(dict)
    graph.add_node("step1", step1)
    graph.add_node("step2", step2)
    graph.add_edge("step1", "step2")
    graph.set_entry_point("step1")
    graph.set_finish_point("step2")
    return graph


if __name__ == "__main__":
    # Test the graph locally
    graph = build_graph().compile()
    result = graph.invoke({"counter": 0, "messages": []})
    print("Result:", result)
    print(f"Counter: {result['counter']}")
    print(f"Messages: {result['messages']}")
    print(f"Final result: {result['final_result']}")
