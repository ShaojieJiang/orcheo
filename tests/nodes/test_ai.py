"""Tests for AI node implementation."""

from unittest.mock import AsyncMock, patch
import pytest
from langchain_core.runnables import RunnableConfig
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
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_prepare_tools(
    mock_mcp_client_class, mock_create_agent, agent, mock_agent, mock_mcp_client
):
    """Test tool preparation."""
    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_tools = [AsyncMock()]
    mock_mcp_client.get_tools.return_value = mock_mcp_tools
    mock_create_agent.return_value = mock_agent

    agent.predefined_tools = ["tool1"]
    agent.workflow_tools = ["workflow1"]
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    await agent.run(state, config)

    mock_mcp_client.get_tools.assert_called_once()
    mock_create_agent.assert_called_once()
    call_kwargs = mock_create_agent.call_args[1]
    assert len(call_kwargs["tools"]) == 3  # 1 predefined + 1 workflow + 1 mcp
