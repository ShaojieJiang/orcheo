"""AI node run-path tests."""

from __future__ import annotations
from unittest.mock import patch
import pytest
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel
from orcheo.graph.state import State


class ResponseModel(BaseModel):
    """Simple response schema exercising response_format path."""

    name: str


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.create_agent")
@patch("orcheo.nodes.ai.MultiServerMCPClient")
async def test_run_without_response_format(
    mock_mcp_client_class, mock_create_agent, agent, mock_agent, mock_mcp_client
):
    """Agent runs end-to-end without response_format configured."""

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
    """Agent run should respect a provided response_format schema."""

    mock_mcp_client_class.return_value = mock_mcp_client
    mock_create_agent.return_value = mock_agent

    agent.response_format = ResponseModel
    state: State = {"messages": [{"role": "user", "content": "test"}]}
    config = RunnableConfig()

    result = await agent.run(state, config)

    mock_create_agent.assert_called_once()
    mock_agent.ainvoke.assert_called_once()
    assert "messages" in result
