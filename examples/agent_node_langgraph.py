import asyncio
from datetime import datetime
from pprint import pprint
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel
from orcheo.graph.state import State
from orcheo.nodes.ai import AgentNode


load_dotenv()


class WeatherResponse(BaseModel):
    """Response model."""

    reply: str
    timestamp: datetime


def build_graph() -> StateGraph:
    """Build the graph."""
    graph = StateGraph(State)
    agent_node = AgentNode(
        name="agent",
        model_name="openai:gpt-4o-mini",
        response_format=WeatherResponse,
    )
    graph.add_node("agent", agent_node)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    return graph


if __name__ == "__main__":
    checkpointer = InMemorySaver()
    workflow = build_graph().compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "123"}}
    result = asyncio.run(
        workflow.ainvoke(
            {"messages": [{"role": "user", "content": "What is the weather?"}]},
            config,
        )
    )
    pprint(result)
