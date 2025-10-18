"""Tests for AI node implementation."""

from unittest.mock import AsyncMock, Mock, patch
import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.ai import (
    Agent,
    AnthropicChat,
    CustomAgent,
    OpenAIChat,
    StructuredOutput,
    TextProcessing,
)


@pytest.fixture
def mock_model():
    model = Mock()
    # Mock the bind_tools method to return itself (not async)
    model.bind_tools.return_value = model
    return model


@pytest.fixture
def mock_agent():
    agent = AsyncMock()
    agent.ainvoke.return_value = {"output": "test result"}
    return agent


@pytest.fixture
def agent():
    return Agent(
        name="test_agent",
        model_settings={"model_name": "gpt-3.5-turbo"},
        system_prompt="Test prompt",
    )


def test_structured_output_json_schema():
    output = StructuredOutput(
        schema_type="json_schema",
        schema_str='{"type": "object", "properties": {"name": {"type": "string"}}}',
    )
    schema = output.get_schema_type()
    assert schema == {"type": "object", "properties": {"name": {"type": "string"}}}


def test_structured_output_pydantic():
    output = StructuredOutput(
        schema_type="pydantic",
        schema_str="""
class TestModel(BaseModel):
    name: str
""",
    )
    schema = output.get_schema_type()
    assert schema.__name__ == "TestModel"


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.init_chat_model")
@patch("orcheo.nodes.ai.create_react_agent")
async def test_run_with_structured_output(
    mock_create_agent, mock_init_model, agent, mock_model, mock_agent
):
    # Setup
    mock_init_model.return_value = mock_model
    mock_create_agent.return_value = mock_agent

    agent.structured_output = {
        "schema_type": "json_schema",
        "schema_str": '{"type": "object", "properties": {"name": {"type": "string"}}}',
    }
    state = State({"input": "test"})
    config = RunnableConfig()

    # Execute
    result = await agent.run(state, config)

    # Verify
    mock_init_model.assert_called_once_with(model_name="gpt-3.5-turbo")
    mock_create_agent.assert_called_once()
    mock_agent.ainvoke.assert_called_once_with(state, config)
    assert result == {"output": "test result"}


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.init_chat_model")
@patch("orcheo.nodes.ai.create_react_agent")
async def test_run_with_memory_checkpointer(
    mock_create_agent, mock_init_model, agent, mock_model, mock_agent
):
    # Setup
    mock_init_model.return_value = mock_model
    mock_create_agent.return_value = mock_agent

    agent.checkpointer = "memory"
    state = State({"input": "test"})
    config = RunnableConfig()

    # Execute
    result = await agent.run(state, config)

    # Verify
    mock_init_model.assert_called_once_with(model_name="gpt-3.5-turbo")
    mock_create_agent.assert_called_once()
    mock_agent.ainvoke.assert_called_once_with(state, config)
    assert result == {"output": "test result"}


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.init_chat_model")
@patch("orcheo.nodes.ai.create_react_agent")
async def test_run_without_checkpointer(
    mock_create_agent, mock_init_model, agent, mock_model, mock_agent
):
    # Setup
    mock_init_model.return_value = mock_model
    mock_create_agent.return_value = mock_agent

    agent.checkpointer = None
    state = State({"input": "test"})
    config = RunnableConfig()

    # Execute
    result = await agent.run(state, config)

    # Verify
    mock_init_model.assert_called_once_with(model_name="gpt-3.5-turbo")
    mock_create_agent.assert_called_once()
    mock_agent.ainvoke.assert_called_once_with(state, config)
    assert result == {"output": "test result"}


@pytest.mark.asyncio
async def test_run_with_invalid_checkpointer(agent):
    # Setup
    agent.checkpointer = "invalid"
    state = State({"input": "test"})
    config = RunnableConfig()

    # Execute and verify
    with pytest.raises(ValueError, match="Invalid checkpointer: invalid"):
        await agent.run(state, config)


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.Agent.run", new_callable=AsyncMock)
async def test_openai_chat_delegates_to_agent(mock_run):
    mock_run.return_value = {"messages": [{"content": "hi"}]}
    node = OpenAIChat(name="openai", model="gpt-4o-mini")
    state = State({"input": "hello"})
    config = RunnableConfig()
    result = await node.run(state, config)
    assert result == {"messages": [{"content": "hi"}]}
    mock_run.assert_awaited()


@pytest.mark.asyncio
@patch("orcheo.nodes.ai.Agent.run", new_callable=AsyncMock)
async def test_anthropic_chat_uses_provider(mock_run):
    mock_run.return_value = {"messages": [{"content": "anthropic"}]}
    node = AnthropicChat(name="anthropic", model="claude")
    state = State({"input": "hello"})
    config = RunnableConfig()
    result = await node.run(state, config)
    assert result == {"messages": [{"content": "anthropic"}]}
    mock_run.assert_awaited()


def test_custom_agent_sets_default_model():
    node = CustomAgent(name="custom", model_settings={})
    assert node.model_settings["model_name"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_text_processing_node():
    processor = TextProcessing(
        name="text",
        operation="replace",
        value="hello world",
        target="world",
        replacement="orcheo",
    )
    state = State({"results": {}})
    output = await processor(state, None)
    assert output["results"]["text"] == "hello orcheo"
