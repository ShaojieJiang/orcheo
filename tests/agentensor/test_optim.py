"""Test module for the Optimizer class."""

from types import SimpleNamespace
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
    with patch("agentensor.optim.create_agent") as mock_create_agent:
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
    with patch("agentensor.optim.create_agent") as mock_create_agent:
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        optimizer.step()

        # Verify the agent was not called since no gradients
        assert mock_agent.invoke.call_count == 0
        assert param1.text == "text1"
        assert param2.text == "text2"


@patch("agentensor.optim.init_chat_model")
@patch("agentensor.tensor.init_chat_model")
def test_optimizer_collects_agent_modules(
    mock_tensor_init, mock_optim_init, mock_graph
):
    """Optimizer should gather parameters from AgentModule nodes."""

    mock_tensor_init.return_value = MagicMock()
    mock_optim_init.return_value = MagicMock()

    class MockModule(AgentModule):
        system_prompt: TextTensor = TextTensor("system", requires_grad=True)
        trainable: TextTensor = TextTensor("trainable", requires_grad=True)

        @property
        def agent(self):  # pragma: no cover - not used by this test
            return MagicMock()

    module = MockModule()
    mock_graph.add_node("agent", module)

    optimizer = Optimizer(mock_graph)

    assert module.trainable in optimizer.params


def test_optimizer_gathers_params_from_multiple_runnable_types() -> None:
    """Ensure module discovery checks all runnable attributes."""

    class ParameterModule(AgentModule):
        trainable: TextTensor

        @property
        def agent(self) -> SimpleNamespace:
            return SimpleNamespace(
                invoke=lambda payload: {"messages": [SimpleNamespace(content="ok")]}
            )

        def example_method(self) -> None:
            return None

    def tensor(name: str, *, grad: bool = True) -> TextTensor:
        return TextTensor(name, requires_grad=grad, model=SimpleNamespace())

    direct_module = ParameterModule(
        system_prompt=tensor("prompt", grad=False),
        trainable=tensor("direct"),
    )
    function_module = ParameterModule(
        system_prompt=tensor("prompt", grad=False),
        trainable=tensor("function"),
    )
    bound_module = ParameterModule(
        system_prompt=tensor("prompt", grad=False),
        trainable=tensor("bound"),
    )

    graph = SimpleNamespace(
        nodes={
            "direct": SimpleNamespace(runnable=direct_module),
            "function": SimpleNamespace(
                runnable=SimpleNamespace(afunc=function_module)
            ),
            "bound": SimpleNamespace(
                runnable=SimpleNamespace(afunc=bound_module.example_method)
            ),
            "ignore": SimpleNamespace(runnable=SimpleNamespace()),
        }
    )

    optimizer = Optimizer(graph, model=SimpleNamespace())

    assert len(optimizer.params) == 3
    assert {param.text for param in optimizer.params} == {"direct", "function", "bound"}


def test_optimizer_collects_duck_typed_get_params() -> None:
    """Optimizer should pick up params from runnables that expose get_params."""

    class DuckRunnable:
        def __init__(self) -> None:
            self.trainable = TextTensor(
                "duck", requires_grad=True, model=SimpleNamespace()
            )

        def get_params(self) -> list[TextTensor]:
            return [self.trainable]

    graph = SimpleNamespace(nodes={"duck": SimpleNamespace(runnable=DuckRunnable())})

    optimizer = Optimizer(graph, model=SimpleNamespace())

    assert len(optimizer.params) == 1
    assert optimizer.params[0].text == "duck"


def test_optimizer_rejects_invalid_params_list() -> None:
    with pytest.raises(TypeError, match="params must contain only TextTensor"):
        Optimizer(
            model=SimpleNamespace(),
            params=[TextTensor("ok", model=SimpleNamespace()), "bad"],
        )


def test_optimizer_rejects_invalid_get_params_return() -> None:
    class BadRunnable:
        def get_params(self) -> str:
            return "not a tensor"

    graph = SimpleNamespace(nodes={"bad": SimpleNamespace(runnable=BadRunnable())})

    with pytest.raises(TypeError, match="get_params\\(\\) must return"):
        Optimizer(graph, model=SimpleNamespace())


def test_optimizer_accepts_single_texttensor_param() -> None:
    """Optimizer should wrap a single TextTensor into a params list."""
    tensor = TextTensor("ok", requires_grad=True, model=SimpleNamespace())

    optimizer = Optimizer(model=SimpleNamespace(), params=tensor)

    assert optimizer.params == [tensor]


def test_optimizer_accepts_empty_params_list() -> None:
    """Optimizer should accept an empty params list."""
    optimizer = Optimizer(model=SimpleNamespace(), params=[])

    assert optimizer.params == []
