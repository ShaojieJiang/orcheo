"""Tests for LangGraph summary serialization."""

from __future__ import annotations
import json
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel
from orcheo.graph.ingestion.summary import summarise_state_graph
from orcheo.graph.state import State
from orcheo.nodes.ai import AgentNode, WorkflowTool


class ToolInput(BaseModel):
    """Input model for the workflow tool."""

    query: str


def _build_tool_graph() -> StateGraph:
    graph = StateGraph(State)
    graph.add_node("noop", lambda state: state)
    graph.add_edge(START, "noop")
    graph.add_edge("noop", END)
    return graph


def test_summarise_state_graph_handles_workflow_tools_graph() -> None:
    graph = StateGraph(State)
    tool_graph = _build_tool_graph()
    agent = AgentNode(
        name="agent",
        ai_model="gpt-4o-mini",
        workflow_tools=[
            WorkflowTool(
                name="tool",
                description="tool desc",
                graph=tool_graph,
                args_schema=ToolInput,
            )
        ],
    )
    graph.add_node("agent", agent)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)

    summary = summarise_state_graph(graph)
    json.dumps(summary)

    agent_node = next(node for node in summary["nodes"] if node["name"] == "agent")
    workflow_tools = agent_node["workflow_tools"]
    assert workflow_tools[0]["graph"]["type"] == "StateGraph"
