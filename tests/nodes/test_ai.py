"""Tests for AI node implementation."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import BaseModel
from orcheo.graph.state import State
from orcheo.nodes.ai import AgentNode


class ResponseModel(BaseModel):
    """Test response model."""

    name: str


@pytest.fixture
def mock_agent():
    """Mock agent."""
    agent = AsyncMock()
    agent.ainvoke.return_value = {
        "messages": [{"role": "assistant", "content": "test"}]
    }
    return agent


@pytest.fixture
def mock_mcp_client():
    """Mock MCP client."""
    client = AsyncMock()
    client.get_tools.return_value = []
    return client


@pytest.fixture
def agent():
    """Agent node fixture."""
    return AgentNode(
        name="test_agent",
        model_name="openai:gpt-4o-mini",
        system_prompt="Test prompt",
    )


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_run_without_response_format(
    mock_mcp_client_class, mock_create_agent, agent, mock_agent, mock_mcp_client
):
    """Test agent run without response format."""
    mock_mcp_client_class.return_value = mock_mcp_client
    mock_create_agent.return_value = mock_agent

    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    result = await agent.run(state, config)

    mock_create_agent.assert_called_once()
    mock_agent.ainvoke.assert_called_once()
    assert "messages" in result


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_run_with_response_format(
    mock_mcp_client_class, mock_create_agent, agent, mock_agent, mock_mcp_client
):
    """Test agent run with response format."""
    mock_mcp_client_class.return_value = mock_mcp_client
    mock_create_agent.return_value = mock_agent

    agent.response_format = ResponseModel
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    result = await agent.run(state, config)

    mock_create_agent.assert_called_once()
    mock_agent.ainvoke.assert_called_once()
    assert "messages" in result


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.tool_registry")
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_prepare_tools(
    mock_mcp_client_class,
    mock_create_agent,
    mock_tool_registry,
    agent,
    mock_agent,
    mock_mcp_client,
):
    """Test tool preparation."""
    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_tools = [AsyncMock()]
    mock_mcp_client.get_tools.return_value = mock_mcp_tools
    mock_create_agent.return_value = mock_agent

    # Mock the tool registry to return a tool factory
    mock_tool = MagicMock(spec=BaseTool)
    mock_tool_factory = MagicMock(return_value=mock_tool)
    mock_tool_registry.get_tool.return_value = mock_tool_factory

    agent.predefined_tools = ["tool1"]
    agent.workflow_tools = []  # Not testing workflow tools in this test
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    await agent.run(state, config)

    mock_mcp_client.get_tools.assert_called_once()
    mock_create_agent.assert_called_once()
    call_kwargs = mock_create_agent.call_args[1]
    assert len(call_kwargs["tools"]) == 2  # 1 predefined + 1 mcp


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.tool_registry")
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_prepare_tools_with_base_tool_instance(
    mock_mcp_client_class,
    mock_create_agent,
    mock_tool_registry,
    agent,
    mock_agent,
    mock_mcp_client,
):
    """Test tool preparation when tool registry returns a BaseTool instance."""
    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

    # Mock the tool registry to return a BaseTool instance directly
    mock_tool = MagicMock(spec=BaseTool)
    mock_tool_registry.get_tool.return_value = mock_tool

    agent.predefined_tools = ["tool1"]
    agent.workflow_tools = []
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    await agent.run(state, config)

    mock_create_agent.assert_called_once()
    call_kwargs = mock_create_agent.call_args[1]
    # Should have 1 tool (the BaseTool instance)
    assert len(call_kwargs["tools"]) == 1
    assert call_kwargs["tools"][0] is mock_tool


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.tool_registry")
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_prepare_tools_with_none_tool(
    mock_mcp_client_class,
    mock_create_agent,
    mock_tool_registry,
    agent,
    mock_agent,
    mock_mcp_client,
):
    """Test tool preparation when tool registry returns None."""
    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

    # Mock the tool registry to return None (tool not found)
    mock_tool_registry.get_tool.return_value = None

    agent.predefined_tools = ["nonexistent_tool"]
    agent.workflow_tools = []
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    await agent.run(state, config)

    mock_create_agent.assert_called_once()
    call_kwargs = mock_create_agent.call_args[1]
    # Should have 0 tools since the tool was not found
    assert len(call_kwargs["tools"]) == 0


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_prepare_tools_with_workflow_tools(
    mock_mcp_client_class, mock_create_agent, agent, mock_agent, mock_mcp_client
):
    """Test tool preparation with workflow tools."""
    from langgraph.graph import StateGraph
    from orcheo.nodes.ai import WorkflowTool

    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

    # Create a simple workflow graph
    workflow_graph = StateGraph(dict)

    def simple_node(state):
        return {"result": "workflow result"}

    workflow_graph.add_node("start", simple_node)
    workflow_graph.set_entry_point("start")
    workflow_graph.set_finish_point("start")

    # Create a WorkflowTool
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
    # Should have 1 tool (the workflow tool)
    assert len(call_kwargs["tools"]) == 1
    assert call_kwargs["tools"][0].name == "test_workflow"
    assert call_kwargs["tools"][0].description == "A test workflow tool"


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_prepare_tools_with_workflow_tools_no_args_schema(
    mock_mcp_client_class, mock_create_agent, agent, mock_agent, mock_mcp_client
):
    """Test tool preparation with workflow tools without args_schema."""
    from langgraph.graph import StateGraph
    from orcheo.nodes.ai import WorkflowTool

    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

    # Create a simple workflow graph
    workflow_graph = StateGraph(dict)

    def simple_node(state):
        return {"result": "workflow result"}

    workflow_graph.add_node("start", simple_node)
    workflow_graph.set_entry_point("start")
    workflow_graph.set_finish_point("start")

    # Create a WorkflowTool without args_schema
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
    # Should have 1 tool (the workflow tool)
    assert len(call_kwargs["tools"]) == 1
    assert call_kwargs["tools"][0].name == "test_workflow_no_schema"


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.tool_registry")
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_prepare_tools_with_non_callable_non_basetool(
    mock_mcp_client_class,
    mock_create_agent,
    mock_tool_registry,
    agent,
    mock_agent,
    mock_mcp_client,
):
    """Test tool preparation when registry returns a non-callable non-BaseTool."""
    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

    # Mock the tool registry to return an invalid type (e.g., a string)
    mock_tool_registry.get_tool.return_value = "not_a_tool"

    agent.predefined_tools = ["invalid_tool"]
    agent.workflow_tools = []
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    await agent.run(state, config)

    mock_create_agent.assert_called_once()
    call_kwargs = mock_create_agent.call_args[1]
    # Should have 0 tools since the invalid tool was skipped
    assert len(call_kwargs["tools"]) == 0


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.tool_registry")
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_prepare_tools_factory_returns_non_basetool(
    mock_mcp_client_class,
    mock_create_agent,
    mock_tool_registry,
    agent,
    mock_agent,
    mock_mcp_client,
):
    """Test tool preparation when factory returns non-BaseTool instance."""
    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

    # Mock the tool registry to return a factory that returns an invalid type
    mock_tool_factory = MagicMock(return_value="not_a_basetool")
    mock_tool_registry.get_tool.return_value = mock_tool_factory

    agent.predefined_tools = ["bad_factory"]
    agent.workflow_tools = []
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    await agent.run(state, config)

    mock_tool_factory.assert_called_once()
    mock_create_agent.assert_called_once()
    call_kwargs = mock_create_agent.call_args[1]
    # Should have 0 tools since the factory returned invalid type
    assert len(call_kwargs["tools"]) == 0


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.tool_registry")
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_prepare_tools_factory_raises_exception(
    mock_mcp_client_class,
    mock_create_agent,
    mock_tool_registry,
    agent,
    mock_agent,
    mock_mcp_client,
):
    """Test tool preparation when factory raises an exception."""
    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

    # Mock the tool registry to return a factory that raises an exception
    mock_tool_factory = MagicMock(side_effect=ValueError("Factory failed"))
    mock_tool_registry.get_tool.return_value = mock_tool_factory

    agent.predefined_tools = ["failing_factory"]
    agent.workflow_tools = []
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    await agent.run(state, config)

    mock_tool_factory.assert_called_once()
    mock_create_agent.assert_called_once()
    call_kwargs = mock_create_agent.call_args[1]
    # Should have 0 tools since the factory raised an exception
    assert len(call_kwargs["tools"]) == 0


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_workflow_tool_compilation_caching(
    mock_mcp_client_class, mock_create_agent, agent, mock_agent, mock_mcp_client
):
    """Test that workflow graphs are compiled once and cached."""
    from langgraph.graph import StateGraph
    from orcheo.nodes.ai import WorkflowTool

    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

    # Create a workflow graph
    workflow_graph = StateGraph(dict)

    def simple_node(state):
        return {"result": "workflow result"}

    workflow_graph.add_node("start", simple_node)
    workflow_graph.set_entry_point("start")
    workflow_graph.set_finish_point("start")

    # Create a WorkflowTool
    workflow_tool = WorkflowTool(
        name="cached_workflow",
        description="A workflow with cached compilation",
        graph=workflow_graph,
    )

    # First call should compile
    compiled_1 = workflow_tool.get_compiled_graph()
    # Second call should return cached version
    compiled_2 = workflow_tool.get_compiled_graph()

    # Should be the same object (cached)
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
    """Test async execution path of workflow tool (line 47)."""
    from langgraph.graph import StateGraph
    from orcheo.nodes.ai import _create_workflow_tool_func

    # Create a workflow graph that captures execution
    workflow_graph = StateGraph(dict)
    execution_tracker = {"executed": False}

    def test_node(state):
        # Track that the workflow was executed via async path
        execution_tracker["executed"] = True
        # Return input to verify data flow
        return {"result": "async_executed", "input_data": state}

    workflow_graph.add_node("process", test_node)
    workflow_graph.set_entry_point("process")
    workflow_graph.set_finish_point("process")

    # Compile the graph
    compiled_graph = workflow_graph.compile()

    # Create tool using the factory function
    tool = _create_workflow_tool_func(
        compiled_graph=compiled_graph,
        name="test_async_tool",
        description="Test async execution",
        args_schema=None,
    )

    result = await tool.ainvoke({"test_input": "test_value"})

    # Verify the async workflow path was executed
    assert execution_tracker["executed"], "Async workflow should have been executed"
    assert "result" in result
    assert result["result"] == "async_executed"


def test_workflow_tool_sync_execution():
    """Test sync execution path of workflow tool (line 51)."""
    from langgraph.graph import StateGraph
    from orcheo.nodes.ai import _create_workflow_tool_func

    # Create a workflow graph that captures execution
    workflow_graph = StateGraph(dict)
    execution_tracker = {"executed": False}

    def test_node(state):
        # Track that the workflow was executed via sync path
        execution_tracker["executed"] = True
        # Return input to verify data flow
        return {"result": "sync_executed", "input_data": state}

    workflow_graph.add_node("process", test_node)
    workflow_graph.set_entry_point("process")
    workflow_graph.set_finish_point("process")

    # Compile the graph
    compiled_graph = workflow_graph.compile()

    # Create tool using the factory function
    tool = _create_workflow_tool_func(
        compiled_graph=compiled_graph,
        name="test_sync_tool",
        description="Test sync execution",
        args_schema=None,
    )

    # Execute the tool synchronously - this exercises line 51:
    # def workflow_sync(**kwargs): return asyncio.run(compiled_graph.ainvoke(kwargs))
    result = tool.invoke({"test_input": "sync_test"})

    # Verify the sync workflow path was executed
    assert execution_tracker["executed"], "Sync workflow should have been executed"
    assert "result" in result
    assert result["result"] == "sync_executed"
