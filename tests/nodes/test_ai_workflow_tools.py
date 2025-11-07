"""Workflow tool behavior tests for AI nodes."""

from __future__ import annotations
from unittest.mock import patch
import pytest
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel
from orcheo.graph.state import State
from orcheo.nodes.ai import WorkflowTool, _create_workflow_tool_func


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_prepare_tools_with_workflow_tools(
    mock_mcp_client_class, mock_create_agent, agent, mock_agent, mock_mcp_client
):
    """Workflow tools should be included when provided."""

    from langgraph.graph import StateGraph

    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

    workflow_graph = StateGraph(dict)

    def simple_node(state):
        return {"result": "workflow result"}

    workflow_graph.add_node("start", simple_node)
    workflow_graph.set_entry_point("start")
    workflow_graph.set_finish_point("start")

    class WorkflowArgs(BaseModel):
        input_value: str

    workflow_tool = WorkflowTool(
        name="test_workflow",
        description="A test workflow tool",
        graph=workflow_graph,
        args_schema=WorkflowArgs,
    )

    agent.predefined_tools = []
    agent.workflow_tools = [workflow_tool]
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    await agent.run(state, config)

    mock_create_agent.assert_called_once()
    call_kwargs = mock_create_agent.call_args[1]
    assert len(call_kwargs["tools"]) == 1
    assert call_kwargs["tools"][0].name == "test_workflow"


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_prepare_tools_with_workflow_tools_no_args_schema(
    mock_mcp_client_class, mock_create_agent, agent, mock_agent, mock_mcp_client
):
    """Workflow tools without schemas should still be wired up."""

    from langgraph.graph import StateGraph

    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

    workflow_graph = StateGraph(dict)

    def simple_node(state):
        return {"result": "workflow result"}

    workflow_graph.add_node("start", simple_node)
    workflow_graph.set_entry_point("start")
    workflow_graph.set_finish_point("start")

    workflow_tool = WorkflowTool(
        name="test_workflow_no_schema",
        description="A test workflow tool without schema",
        graph=workflow_graph,
        args_schema=None,
    )

    agent.predefined_tools = []
    agent.workflow_tools = [workflow_tool]
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    await agent.run(state, config)

    mock_create_agent.assert_called_once()
    call_kwargs = mock_create_agent.call_args[1]
    assert len(call_kwargs["tools"]) == 1
    assert call_kwargs["tools"][0].name == "test_workflow_no_schema"


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_workflow_tool_compilation_caching(
    mock_mcp_client_class, mock_create_agent, agent, mock_agent, mock_mcp_client
):
    """WorkflowTool should compile graphs once and reuse them."""

    from langgraph.graph import StateGraph

    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

    workflow_graph = StateGraph(dict)

    def simple_node(state):
        return {"result": "workflow result"}

    workflow_graph.add_node("start", simple_node)
    workflow_graph.set_entry_point("start")
    workflow_graph.set_finish_point("start")

    workflow_tool = WorkflowTool(
        name="cached_workflow",
        description="A workflow with cached compilation",
        graph=workflow_graph,
    )

    compiled_1 = workflow_tool.get_compiled_graph()
    compiled_2 = workflow_tool.get_compiled_graph()
    assert compiled_1 is compiled_2

    agent.predefined_tools = []
    agent.workflow_tools = [workflow_tool]
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    await agent.run(state, config)

    mock_create_agent.assert_called_once()
    call_kwargs = mock_create_agent.call_args[1]
    assert len(call_kwargs["tools"]) == 1


@pytest.mark.asyncio
async def test_workflow_tool_async_execution():
    """Async execution path should invoke compiled graph via ainvoke."""

    from langgraph.graph import StateGraph

    workflow_graph = StateGraph(dict)
    execution_tracker = {"executed": False}

    def test_node(state):
        execution_tracker["executed"] = True
        return {"result": "async_executed", "input_data": state}

    workflow_graph.add_node("process", test_node)
    workflow_graph.set_entry_point("process")
    workflow_graph.set_finish_point("process")

    compiled_graph = workflow_graph.compile()

    tool = _create_workflow_tool_func(
        compiled_graph=compiled_graph,
        name="test_async_tool",
        description="Test async execution",
        args_schema=None,
    )

    result = await tool.ainvoke({"test_input": "test_value"})

    assert execution_tracker["executed"]
    assert result["result"] == "async_executed"


def test_workflow_tool_sync_execution():
    """Sync execution path should funnel through asyncio.run."""

    from langgraph.graph import StateGraph

    workflow_graph = StateGraph(dict)
    execution_tracker = {"executed": False}

    def test_node(state):
        execution_tracker["executed"] = True
        return {"result": "sync_executed", "input_data": state}

    workflow_graph.add_node("process", test_node)
    workflow_graph.set_entry_point("process")
    workflow_graph.set_finish_point("process")

    compiled_graph = workflow_graph.compile()

    tool = _create_workflow_tool_func(
        compiled_graph=compiled_graph,
        name="test_sync_tool",
        description="Test sync execution",
        args_schema=None,
    )

    result = tool.invoke({"test_input": "sync_test"})

    assert execution_tracker["executed"]
    assert result["result"] == "sync_executed"
