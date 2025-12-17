"""Test module for the Trainer class."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic_evals import Dataset
from pydantic_graph import Graph
from agentensor.module import AgentModule
from agentensor.optim import Optimizer
from agentensor.tensor import TextTensor
from agentensor.train import Trainer


@pytest.fixture
def mock_graph():
    """Create a mock graph for testing."""
    mock_graph = MagicMock(spec=Graph)
    return mock_graph


@pytest.fixture
def mock_dataset():
    """Create a mock dataset for testing."""
    mock_dataset = MagicMock(spec=Dataset)
    return mock_dataset


@pytest.fixture
def mock_optimizer():
    """Create a mock optimizer for testing."""
    mock_optimizer = MagicMock(spec=Optimizer)
    mock_optimizer.params = []  # Add params attribute
    return mock_optimizer


@pytest.fixture
@patch("agentensor.module.init_chat_model")
@patch("agentensor.tensor.init_chat_model")
def mock_module_class(mock_tensor_init, mock_module_init):
    """Create a mock module class for testing."""
    # Mock the model initialization
    mock_tensor_init.return_value = MagicMock()
    mock_module_init.return_value = MagicMock()

    class MockModule(AgentModule):
        system_prompt: TextTensor = TextTensor("test", requires_grad=True)

        async def run(self, state: dict) -> dict:
            return state

        def get_agent(self):
            """Dummy get_agent method for testing."""
            pass

    return MockModule


@pytest.mark.asyncio
async def test_trainer_initialization(
    mock_graph, mock_dataset, mock_optimizer, mock_module_class
):
    """Test Trainer initialization."""
    trainer = Trainer(
        graph=mock_graph,
        train_dataset=mock_dataset,
        optimizer=mock_optimizer,
        epochs=10,
        stop_threshold=0.95,
    )

    assert trainer.graph == mock_graph
    assert trainer.train_dataset == mock_dataset
    assert trainer.optimizer == mock_optimizer
    assert trainer.epochs == 10
    assert trainer.stop_threshold == 0.95


@pytest.mark.asyncio
async def test_trainer_step(
    mock_graph, mock_dataset, mock_optimizer, mock_module_class
):
    """Test the step method of Trainer."""
    # Setup
    trainer = Trainer(
        graph=mock_graph,
        train_dataset=mock_dataset,
        optimizer=mock_optimizer,
        epochs=10,
    )

    # Mock the graph's run method
    mock_graph.ainvoke = AsyncMock()

    # Create a proper mock TextTensor for the return value
    with patch("agentensor.tensor.init_chat_model") as mock_tensor_init:
        mock_tensor_init.return_value = MagicMock()
        expected_output = TextTensor("test output")
        mock_graph.ainvoke.return_value = {"output": expected_output}

        # Test step
        input_tensor = TextTensor("test input")
        result = await trainer.forward(input_tensor)

        # Verify
        assert isinstance(result, TextTensor)
        assert result.text == "test output"
        mock_graph.ainvoke.assert_called_once()


def test_trainer_train(mock_graph, mock_dataset, mock_optimizer, mock_module_class):
    """Test the train method of Trainer."""
    # Setup
    trainer = Trainer(
        graph=mock_graph,
        train_dataset=mock_dataset,
        optimizer=mock_optimizer,
        epochs=2,
    )

    # Mock dataset evaluation
    mock_report = MagicMock()
    mock_report.cases = []
    mock_report.averages.return_value.assertions = 0.96  # Above stop threshold
    mock_dataset.evaluate_sync.return_value = mock_report

    # Run training
    trainer.train()

    # Verify
    assert mock_dataset.evaluate_sync.call_count == 1
    assert mock_optimizer.step.call_count == 1
    assert mock_optimizer.zero_grad.call_count == 1


@patch("agentensor.tensor.init_chat_model")
def test_trainer_train_with_failed_cases(
    mock_tensor_init, mock_graph, mock_dataset, mock_optimizer, mock_module_class
):
    """Test the train method with failed cases that need backward pass."""
    # Mock the model initialization
    mock_tensor_init.return_value = MagicMock()

    # Setup
    trainer = Trainer(
        graph=mock_graph,
        train_dataset=mock_dataset,
        optimizer=mock_optimizer,
        epochs=2,
    )

    # Create a mock case with failed assertions
    mock_case = MagicMock()
    mock_case.output = TextTensor("test output", requires_grad=True)
    mock_case.assertions = {
        "test1": MagicMock(value=False, reason="error1"),
        "test2": MagicMock(value=True, reason=None),
    }

    # Mock dataset evaluation
    mock_report = MagicMock()
    mock_report.cases = [mock_case]
    mock_report.averages.return_value.assertions = 0.5  # Below stop threshold
    mock_dataset.evaluate_sync.return_value = mock_report

    # Run training
    trainer.train()

    # Verify
    assert mock_dataset.evaluate_sync.call_count == 2  # Called for each epoch
    assert mock_optimizer.step.call_count == 2
    assert mock_optimizer.zero_grad.call_count == 2


def test_trainer_early_stopping(
    mock_graph, mock_dataset, mock_optimizer, mock_module_class
):
    """Test early stopping when performance threshold is reached."""
    # Setup
    trainer = Trainer(
        graph=mock_graph,
        train_dataset=mock_dataset,
        optimizer=mock_optimizer,
        epochs=10,
        stop_threshold=0.95,
    )

    # Mock dataset evaluation with high performance
    mock_report = MagicMock()
    mock_report.cases = []
    mock_report.averages.return_value.assertions = 0.96  # Above stop threshold
    mock_dataset.evaluate_sync.return_value = mock_report

    # Run training
    trainer.train()

    # Verify early stopping
    assert mock_dataset.evaluate_sync.call_count == 1  # Only one epoch before stopping
    assert mock_optimizer.step.call_count == 1
    assert mock_optimizer.zero_grad.call_count == 1


@patch("agentensor.tensor.init_chat_model")
def test_trainer_train_with_no_losses(
    mock_tensor_init, mock_graph, mock_dataset, mock_optimizer, mock_module_class
):
    """Test the train method when all assertions pass and there are no losses."""
    # Mock the model initialization
    mock_tensor_init.return_value = MagicMock()

    # Setup
    trainer = Trainer(
        graph=mock_graph,
        train_dataset=mock_dataset,
        optimizer=mock_optimizer,
        epochs=2,
    )

    # Create a mock case with all passing assertions
    mock_case = MagicMock()
    mock_case.output = TextTensor("test output", requires_grad=True)
    mock_case.assertions = {
        "test1": MagicMock(value=True, reason=None),
        "test2": MagicMock(value=True, reason=None),
    }

    # Mock dataset evaluation
    mock_report = MagicMock()
    mock_report.cases = [mock_case]
    mock_report.averages.return_value.assertions = (
        0.5  # Below stop threshold to continue training
    )
    mock_dataset.evaluate_sync.return_value = mock_report

    # Run training
    trainer.train()

    # Verify
    assert mock_dataset.evaluate_sync.call_count == 2  # Called for each epoch
    assert mock_optimizer.step.call_count == 2
    assert mock_optimizer.zero_grad.call_count == 2


def test_trainer_test(mock_graph, mock_dataset, mock_optimizer, mock_module_class):
    """Test the test method of Trainer."""
    # Create test dataset
    test_dataset = MagicMock(spec=Dataset)
    mock_report = MagicMock()
    test_dataset.evaluate_sync.return_value = mock_report

    # Setup trainer with test_dataset
    trainer = Trainer(
        graph=mock_graph,
        train_dataset=mock_dataset,
        test_dataset=test_dataset,
        optimizer=mock_optimizer,
        epochs=2,
    )

    # Run test (should not return anything)
    result = trainer.test()

    # Verify
    assert result is None  # test method doesn't return anything
    test_dataset.evaluate_sync.assert_called_once_with(trainer.forward)
    mock_report.print.assert_called_once_with(
        include_input=True, include_output=True, include_durations=True
    )
