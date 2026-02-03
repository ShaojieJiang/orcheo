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


def test_serialise_fallback_nested_basemodel() -> None:
    from orcheo.graph.ingestion.summary import _serialise_fallback

    class Inner(BaseModel):
        value: int = 1

    result = _serialise_fallback(Inner())
    assert result == {"value": 1}


def test_serialise_fallback_compiled_state_graph() -> None:
    from orcheo.graph.ingestion.summary import _serialise_fallback

    graph = StateGraph(State)
    graph.add_node("noop", lambda state: state)
    graph.add_edge(START, "noop")
    graph.add_edge("noop", END)
    compiled = graph.compile()
    result = _serialise_fallback(compiled)
    assert result == {"type": "CompiledStateGraph"}


def test_serialise_fallback_set() -> None:
    from orcheo.graph.ingestion.summary import _serialise_fallback

    result = _serialise_fallback({1, 2})
    assert isinstance(result, list)
    assert sorted(result) == ["1", "2"]


def test_serialise_fallback_unknown_type() -> None:
    from orcheo.graph.ingestion.summary import _serialise_fallback

    class Custom:
        pass

    obj = Custom()
    result = _serialise_fallback(obj)
    assert "Custom" in result
