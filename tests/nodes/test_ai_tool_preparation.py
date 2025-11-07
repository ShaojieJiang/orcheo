"""Tool preparation tests for AI nodes."""

from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from orcheo.graph.state import State


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
    """Agent should merge predefined and MCP tools."""

    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_tools = [AsyncMock()]
    mock_mcp_client.get_tools.return_value = mock_mcp_tools
    mock_create_agent.return_value = mock_agent

    mock_tool = MagicMock(spec=BaseTool)
    mock_tool_factory = MagicMock(return_value=mock_tool)
    mock_tool_registry.get_tool.return_value = mock_tool_factory

    agent.predefined_tools = ["tool1"]
    agent.workflow_tools = []
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    await agent.run(state, config)

    mock_mcp_client.get_tools.assert_called_once()
    mock_create_agent.assert_called_once()
    call_kwargs = mock_create_agent.call_args[1]
    assert len(call_kwargs["tools"]) == 2


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
    """Direct BaseTool instances should be used without wrapping."""

    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

    mock_tool = MagicMock(spec=BaseTool)
    mock_tool_registry.get_tool.return_value = mock_tool

    agent.predefined_tools = ["tool1"]
    agent.workflow_tools = []
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    await agent.run(state, config)

    mock_create_agent.assert_called_once()
    call_kwargs = mock_create_agent.call_args[1]
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
    """Missing tools should be skipped gracefully."""

    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

    mock_tool_registry.get_tool.return_value = None

    agent.predefined_tools = ["nonexistent_tool"]
    agent.workflow_tools = []
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    await agent.run(state, config)

    mock_create_agent.assert_called_once()
    call_kwargs = mock_create_agent.call_args[1]
    assert len(call_kwargs["tools"]) == 0


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
    """Invalid registry values should be ignored."""

    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

    mock_tool_registry.get_tool.return_value = "not_a_tool"

    agent.predefined_tools = ["invalid_tool"]
    agent.workflow_tools = []
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    await agent.run(state, config)

    mock_create_agent.assert_called_once()
    call_kwargs = mock_create_agent.call_args[1]
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
    """Factories returning non-BaseTool instances should be filtered."""

    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

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
    """Factories raising should not break tool assembly."""

    mock_mcp_client_class.return_value = mock_mcp_client
    mock_mcp_client.get_tools.return_value = []
    mock_create_agent.return_value = mock_agent

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
    assert len(call_kwargs["tools"]) == 0
