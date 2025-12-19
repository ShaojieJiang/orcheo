"""Tests for the loss module."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic_ai import models
from pydantic_evals.evaluators import EvaluatorContext
from agentensor.loss import LLMTensorJudge
from agentensor.tensor import TextTensor


@pytest.fixture
def mock_openai():
    """Mock the OpenAI client."""
    with patch("openai.AsyncOpenAI") as mock:
        mock.return_value = MagicMock()
        yield mock


@pytest.fixture
def mock_judge_input_output():
    """Mock the judge_input_output function."""
    with patch("agentensor.loss.judge_input_output") as mock:
        mock.return_value = AsyncMock(pass_=True, reason="Test reason")
        yield mock


@pytest.fixture
def mock_judge_output():
    """Mock the judge_output function."""
    with patch("agentensor.loss.judge_output") as mock:
        mock.return_value = AsyncMock(pass_=True, reason="Test reason")
        yield mock


@pytest.fixture
@patch("agentensor.tensor.init_chat_model")
def evaluator_context(mock_init_chat_model, mock_openai):
    """Create a test evaluator context."""
    # Mock the model initialization
    mock_init_chat_model.return_value = MagicMock()

    return EvaluatorContext(
        name="test_evaluator",
        inputs=TextTensor(text="test input"),
        output=TextTensor(text="test output"),
        expected_output=TextTensor(text="expected output"),
        duration=0.0,
        _span_tree=MagicMock(),
        attributes={},
        metrics={},
        metadata={},
    )


@pytest.mark.asyncio
async def test_llm_tensor_judge_evaluate_with_input(
    mock_judge_input_output, evaluator_context
):
    """Test LLMTensorJudge evaluate method with input included."""
    judge = LLMTensorJudge(rubric="test rubric", include_input=True)
    result = await judge.evaluate(evaluator_context)

    mock_judge_input_output.assert_called_once_with(
        "test input", "test output", "test rubric", None
    )
    assert result.value is True
    assert result.reason == "Test reason"


@pytest.mark.asyncio
async def test_llm_tensor_judge_evaluate_without_input(
    mock_judge_output, evaluator_context
):
    """Test LLMTensorJudge evaluate method without input."""
    judge = LLMTensorJudge(rubric="test rubric", include_input=False)
    result = await judge.evaluate(evaluator_context)

    mock_judge_output.assert_called_once_with("test output", "test rubric", None)
    assert result.value is True
    assert result.reason == "Test reason"


def test_llm_tensor_judge_build_serialization_arguments():
    """Test LLMTensorJudge build_serialization_arguments method."""
    # Test with string model name
    judge = LLMTensorJudge(rubric="test rubric", model="gpt-4")
    args = judge.build_serialization_arguments()
    assert args["model"] == "gpt-4"

    # Test with Model instance
    model = MagicMock(spec=models.Model)
    model.system = "openai"
    model.model_name = "gpt-4"
    judge = LLMTensorJudge(rubric="test rubric", model=model)
    args = judge.build_serialization_arguments()
    assert args["model"] == "openai:gpt-4"
