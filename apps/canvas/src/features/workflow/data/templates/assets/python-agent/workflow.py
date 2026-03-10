from langgraph.graph import StateGraph
from orcheo.graph.state import State
from orcheo.nodes.ai import AgentNode


def orcheo_workflow() -> StateGraph:
    """Build a Python agent workflow."""
    graph = StateGraph(State)
    agent = AgentNode(
        name="ai_agent",
        ai_model="openai:gpt-4o-mini",
        system_prompt="You are a helpful assistant for workflow demos.",
        model_kwargs={"api_key": "[[openai_api_key]]"},
    )
    graph.add_node("ai_agent", agent)
    graph.set_entry_point("ai_agent")
    graph.set_finish_point("ai_agent")
    return graph
