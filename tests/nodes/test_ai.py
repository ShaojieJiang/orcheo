"""Tests for AI node implementation."""

from unittest.mock import Mock, patch
import pytest
from langchain_core.runnables import RunnableConfig
from aic_flow.graph.state import State
from aic_flow.nodes.ai import Agent


@pytest.fixture
def mock_model():
    return Mock()


@pytest.fixture
def mock_agent():
    return Mock()


@pytest.fixture
def agent():
    return Agent(
        name="test_agent",
        model_config={"model_name": "gpt-3.5-turbo"},
        system_prompt="Test prompt",
    )


@patch("aic_flow.nodes.ai.init_chat_model")
@patch("aic_flow.nodes.ai.create_react_agent")
def test_run_with_memory_checkpointer(
    mock_create_agent, mock_init_model, agent, mock_model, mock_agent
):
    # Setup
    mock_init_model.return_value = mock_model
    mock_create_agent.return_value = mock_agent
    mock_agent.invoke.return_value = {"output": "test result"}

    agent.checkpointer = "memory"
    state = State({"input": "test"})
    config = RunnableConfig()

    # Execute
    result = agent.run(state, config)

    # Verify
    mock_init_model.assert_called_once_with(model_name="gpt-3.5-turbo")
    mock_create_agent.assert_called_once()
    mock_agent.invoke.assert_called_once_with({"input": state}, config)
    assert result == {"output": "test result"}


@patch("aic_flow.nodes.ai.init_chat_model")
@patch("aic_flow.nodes.ai.create_react_agent")
def test_run_without_checkpointer(
    mock_create_agent, mock_init_model, agent, mock_model, mock_agent
):
    # Setup
    mock_init_model.return_value = mock_model
    mock_create_agent.return_value = mock_agent
    mock_agent.invoke.return_value = {"output": "test result"}

    agent.checkpointer = None
    state = State({"input": "test"})
    config = RunnableConfig()

    # Execute
    result = agent.run(state, config)

    # Verify
    mock_init_model.assert_called_once_with(model_name="gpt-3.5-turbo")
    mock_create_agent.assert_called_once()
    mock_agent.invoke.assert_called_once_with({"input": state}, config)
    assert result == {"output": "test result"}


def test_run_with_invalid_checkpointer(agent):
    # Setup
    agent.checkpointer = "invalid"
    state = State({"input": "test"})
    config = RunnableConfig()

    # Execute and verify
    with pytest.raises(ValueError, match="Invalid checkpointer: invalid"):
        agent.run(state, config)
