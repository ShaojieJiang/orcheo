"""Shared fixtures for node tests."""

from __future__ import annotations
from unittest.mock import AsyncMock
import pytest
from orcheo.nodes.ai import AgentNode


@pytest.fixture
def mock_agent():
    """Async agent mock with default assistant response."""

    agent = AsyncMock()
    agent.ainvoke.return_value = {
        "messages": [{"role": "assistant", "content": "test"}]
    }
    return agent


@pytest.fixture
def mock_mcp_client():
    """MCP client mock returning no tools by default."""

    client = AsyncMock()
    client.get_tools.return_value = []
    return client


@pytest.fixture
def agent():
    """AgentNode fixture shared across AI node tests."""

    return AgentNode(
        name="test_agent",
        model_name="openai:gpt-4o-mini",
        system_prompt="Test prompt",
    )
