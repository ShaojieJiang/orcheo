"""ChatKit agent workflow.

This workflow exposes a single AgentNode suitable for ChatKit's public UI.
ChatKit sends message/history payloads; the AgentNode normalizes them into
LangChain messages and generates a reply.
"""

from langgraph.graph import END, START, StateGraph
from orcheo.graph.state import State
from orcheo.nodes.ai import AgentNode


DEFAULT_MODEL = "openai:gpt-4o-mini"


def build_graph() -> StateGraph:
    """Build the ChatKit agent workflow."""
    graph = StateGraph(State)

    agent_node = AgentNode(
        name="agent",
        ai_model=DEFAULT_MODEL,
        model_kwargs={"api_key": "[[openai_api_key]]"},
        system_prompt="{{config.configurable.system_prompt}}",
    )

    graph.add_node("agent", agent_node)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    return graph
