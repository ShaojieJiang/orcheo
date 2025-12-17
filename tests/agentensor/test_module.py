"""Test module for the Module class."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from agentensor.module import AgentModule
from agentensor.tensor import TextTensor


@patch("agentensor.module.init_chat_model")
@patch("agentensor.tensor.init_chat_model")
def test_module_get_params(mock_tensor_init, mock_module_init):
    """Test AgentModule.get_params() method."""
    # Mock the model initialization
    mock_tensor_init.return_value = MagicMock()
    mock_module_init.return_value = MagicMock()

    class TestModule(AgentModule):
        system_prompt: TextTensor = TextTensor("param1", requires_grad=True)
        param2: TextTensor = TextTensor("param2", requires_grad=False)
        param3: TextTensor = TextTensor("param3", requires_grad=True)
        model: str = "openai:gpt-4o"
        non_param: str = "not a tensor"

        @property
        def agent(self):
            """Mock agent property for testing."""
            return MagicMock()

    module = TestModule()
    params = module.get_params()

    assert len(params) == 2
    assert all(isinstance(p, TextTensor) for p in params)
    assert all(p.requires_grad for p in params)
    assert params[0].text == "param1"
    assert params[1].text == "param3"


@patch("agentensor.module.init_chat_model")
@patch("agentensor.tensor.init_chat_model")
def test_module_get_params_empty(mock_tensor_init, mock_module_init):
    """Test AgentModule.get_params() with no parameters."""
    # Mock the model initialization
    mock_tensor_init.return_value = MagicMock()
    mock_module_init.return_value = MagicMock()

    class EmptyModule(AgentModule):
        system_prompt: TextTensor = TextTensor("param", requires_grad=False)
        non_param: str = "not a tensor"

        @property
        def agent(self):
            """Mock agent property for testing."""
            return MagicMock()

    module = EmptyModule()
    params = module.get_params()

    assert len(params) == 0


@patch("agentensor.module.init_chat_model")
@patch("agentensor.tensor.init_chat_model")
def test_module_get_params_inheritance(mock_tensor_init, mock_module_init):
    """Test AgentModule.get_params() with inheritance."""
    # Mock the model initialization
    mock_tensor_init.return_value = MagicMock()
    mock_module_init.return_value = MagicMock()

    class ParentModule(AgentModule):
        system_prompt: TextTensor = TextTensor("parent", requires_grad=True)

        @property
        def agent(self):
            """Mock agent property for testing."""
            return MagicMock()

    class ChildModule(ParentModule):
        child_param: TextTensor = TextTensor("child", requires_grad=True)

        @property
        def agent(self):
            """Mock agent property for testing."""
            return MagicMock()

    module = ChildModule()
    params = module.get_params()

    assert len(params) == 2
    assert all(isinstance(p, TextTensor) for p in params)
    assert all(p.requires_grad for p in params)
    assert {p.text for p in params} == {"parent", "child"}


@patch("agentensor.module.init_chat_model")
@patch("agentensor.tensor.init_chat_model")
@pytest.mark.asyncio
async def test_module_call(mock_tensor_init, mock_module_init):
    # Mock the model initialization
    mock_tensor_init.return_value = MagicMock()
    mock_module_init.return_value = MagicMock()

    class TestModule(AgentModule):
        system_prompt: TextTensor = TextTensor("system prompt", requires_grad=True)

        @property
        def agent(self):
            """Mock agent property for testing."""
            mock_agent = AsyncMock()
            mock_result = {"messages": [MagicMock()]}
            mock_result["messages"][-1].content = "Output text"
            mock_agent.ainvoke.return_value = mock_result
            return mock_agent

    module = TestModule()

    result = await module({"output": TextTensor("Input text")})
    assert isinstance(result["output"], TextTensor)
    assert result["output"].text == "Output text"
