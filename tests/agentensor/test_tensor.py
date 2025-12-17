"""Test module for the TextTensor class."""

from unittest.mock import MagicMock, patch
import pytest
from agentensor.tensor import TextTensor


@pytest.fixture
def mock_model():
    """Fixture to provide a mock language model."""
    return MagicMock()


@patch("agentensor.tensor.init_chat_model")
def test_text_tensor_requires_grad_false(mock_init_chat_model):
    """Test TextTensor behavior when requires_grad is False."""
    # Mock the model initialization
    mock_init_chat_model.return_value = MagicMock()

    # Create a tensor with requires_grad=False
    tensor = TextTensor("test text", requires_grad=False)

    # Verify initial state
    assert tensor.text == "test text"
    assert tensor.requires_grad is False
    assert tensor.text_grad == ""
    assert tensor.parents == []

    # Try to perform backward pass
    tensor.backward("some gradient")

    # Verify that the gradient was not set and no backward pass was performed
    assert tensor.text_grad == ""


@patch("agentensor.tensor.init_chat_model")
def test_backward_without_grad_and_requires_grad_false(mock_init_chat_model):
    """Test backward pass when requires_grad is False and grad is empty string."""
    # Mock the model initialization
    mock_init_chat_model.return_value = MagicMock()

    # Create a TextTensor with requires_grad=False
    tensor = TextTensor("test text")

    # Call backward with empty grad
    tensor.backward("")

    # Verify that text_grad remains empty
    assert tensor.text_grad == ""

    # Verify that no gradient was propagated to parents
    assert len(tensor.parents) == 0


@patch("agentensor.tensor.init_chat_model")
def test_backward_with_parent_requires_grad_false(mock_init_chat_model):
    """Test backward pass when parent tensor has requires_grad=False."""
    # Mock the model initialization
    mock_init_chat_model.return_value = MagicMock()

    # Create parent tensor with requires_grad=False
    parent_tensor = TextTensor("parent text", requires_grad=False)

    # Create child tensor with requires_grad=True and parent
    child_tensor = TextTensor("child text", parents=[parent_tensor], requires_grad=True)

    # Perform backward pass
    child_tensor.backward("some gradient")

    # Verify child tensor got the gradient
    assert child_tensor.text_grad == "some gradient"

    # Verify parent tensor did not get updated
    assert parent_tensor.text_grad == ""


@patch("agentensor.tensor.init_chat_model")
def test_backward_with_parent_requires_grad_true(mock_init_chat_model):
    """Test backward pass when parent tensor has requires_grad=True."""
    # Mock the model initialization
    mock_init_chat_model.return_value = MagicMock()

    # Create parent tensor with requires_grad=True
    parent_tensor = TextTensor("parent text", requires_grad=True)

    # Create child tensor with requires_grad=True and parent
    child_tensor = TextTensor("child text", parents=[parent_tensor], requires_grad=True)

    # Mock the agent's response for gradient calculation
    with patch("agentensor.tensor.create_react_agent") as mock_create_agent:
        mock_agent = MagicMock()
        mock_result = {"messages": [MagicMock()]}
        mock_result["messages"][-1].content = "parent gradient"
        mock_agent.invoke.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        # Perform backward pass
        child_tensor.backward("some gradient")

        # Verify child tensor got the gradient
        assert child_tensor.text_grad == "some gradient"

        # Verify parent tensor got updated with calculated gradient
        assert parent_tensor.text_grad == "parent gradient"

        # Verify agent was called
        mock_agent.invoke.assert_called_once()


@patch("agentensor.tensor.init_chat_model")
def test_calc_grad(mock_init_chat_model):
    """Test the calc_grad method."""
    # Mock the model initialization
    mock_init_chat_model.return_value = MagicMock()

    # Create a tensor
    tensor = TextTensor("test text")

    # Mock the agent's response
    with patch("agentensor.tensor.create_react_agent") as mock_create_agent:
        mock_agent = MagicMock()
        mock_result = {"messages": [MagicMock()]}
        mock_result["messages"][-1].content = "improved input"
        mock_agent.invoke.return_value = mock_result
        mock_create_agent.return_value = mock_agent

        # Call calc_grad
        result = tensor.calc_grad("input text", "output text", "feedback")

        # Verify the result
        assert result == "improved input"

        # Verify agent was called with correct arguments
        mock_agent.invoke.assert_called_once()
        call_args = mock_agent.invoke.call_args[0][0]
        assert "input text" in call_args["messages"][0].content
        assert "output text" in call_args["messages"][0].content
        assert "feedback" in call_args["messages"][0].content
        assert "How should I improve the input" in call_args["messages"][0].content


@patch("agentensor.tensor.init_chat_model")
def test_str(mock_init_chat_model):
    """Test the __str__ method."""
    # Mock the model initialization
    mock_init_chat_model.return_value = MagicMock()

    # Create a tensor with some text
    tensor = TextTensor("test text")

    # Test string representation
    assert str(tensor) == "test text"

    # Test with different text
    tensor = TextTensor("another text")
    assert str(tensor) == "another text"
