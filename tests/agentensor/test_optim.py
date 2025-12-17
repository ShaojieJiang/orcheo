"""Test module for the Optimizer class."""

from unittest.mock import MagicMock, patch
import pytest
from langgraph.graph import StateGraph
from agentensor.module import AgentModule
from agentensor.optim import Optimizer
from agentensor.tensor import TextTensor


@pytest.fixture
def mock_graph():
    """Create a mock graph for testing."""
    mock_graph = StateGraph(dict)
    return mock_graph


@pytest.fixture
@patch("agentensor.tensor.init_chat_model")
def mock_module_class(mock_init_chat_model):
    """Create a mock module class for testing."""
    # Mock the model initialization
    mock_init_chat_model.return_value = MagicMock()

    class MockModule(AgentModule):
        system_prompt: TextTensor = TextTensor("system", requires_grad=True)
        param1: TextTensor = TextTensor("initial text 1", requires_grad=True)
        param2: TextTensor = TextTensor("initial text 2", requires_grad=True)

        @property
        def agent(self):
            """Mock agent property for testing."""
            return MagicMock()

    return MockModule


@patch("agentensor.optim.init_chat_model")
def test_optimizer_initialization(mock_init_chat_model, mock_graph):
    """Test Optimizer initialization."""
    # Mock the model initialization
    mock_init_chat_model.return_value = MagicMock()

    optimizer = Optimizer(mock_graph)
    assert hasattr(optimizer, "agent")
    assert isinstance(optimizer.params, list)


@patch("agentensor.optim.init_chat_model")
@patch("agentensor.tensor.init_chat_model")
def test_optimizer_zero_grad(mock_tensor_init, mock_optim_init, mock_graph):
    """Test zero_grad method."""
    # Mock the model initialization
    mock_tensor_init.return_value = MagicMock()
    mock_optim_init.return_value = MagicMock()

    optimizer = Optimizer(mock_graph)
    param1 = TextTensor("text1", requires_grad=True)
    param2 = TextTensor("text2", requires_grad=True)

    # Set some gradients
    param1.gradients = ["grad1"]
    param2.gradients = ["grad2"]

    optimizer.params = [param1, param2]
    optimizer.zero_grad()

    assert param1.text_grad == ""
    assert param2.text_grad == ""


@patch("agentensor.optim.init_chat_model")
@patch("agentensor.tensor.init_chat_model")
def test_optimizer_step(mock_tensor_init, mock_optim_init, mock_graph):
    """Test step method."""
    # Mock the model initialization
    mock_tensor_init.return_value = MagicMock()
    mock_optim_init.return_value = MagicMock()

    optimizer = Optimizer(mock_graph)
    param1 = TextTensor("text1", requires_grad=True)
    param2 = TextTensor("text2", requires_grad=True)

    # Set some gradients
    param1.gradients = ["grad1"]
    param2.gradients = ["grad2"]

    optimizer.params = [param1, param2]

    # Mock the agent's response
    with patch("agentensor.optim.create_react_agent") as mock_create_agent:
        mock_agent = MagicMock()
        mock_result = {"messages": [MagicMock()]}
        mock_result["messages"][-1].content = "optimized text"
        mock_agent.invoke.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        optimizer.step()

        # Verify the agent was called for each parameter with gradient
        assert mock_agent.invoke.call_count == 2
        assert param1.text == "optimized text"
        assert param2.text == "optimized text"


@patch("agentensor.optim.init_chat_model")
@patch("agentensor.tensor.init_chat_model")
def test_optimizer_step_no_grad(mock_tensor_init, mock_optim_init, mock_graph):
    """Test step method when there are no gradients."""
    # Mock the model initialization
    mock_tensor_init.return_value = MagicMock()
    mock_optim_init.return_value = MagicMock()

    optimizer = Optimizer(mock_graph)
    param1 = TextTensor("text1", requires_grad=True)
    param2 = TextTensor("text2", requires_grad=True)

    optimizer.params = [param1, param2]

    # Mock the agent
    with patch("agentensor.optim.create_react_agent") as mock_create_agent:
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        optimizer.step()

        # Verify the agent was not called since no gradients
        assert mock_agent.invoke.call_count == 0
        assert param1.text == "text1"
        assert param2.text == "text2"
