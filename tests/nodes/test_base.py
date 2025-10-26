"""Tests for base node implementation."""

from typing import Any
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.types import Send
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import AINode, DecisionNode, TaskNode


class MockTaskNode(TaskNode):
    """Mock task node implementation."""

    input_var: str = Field(description="Input variable for testing")

    def __init__(self, name: str, input_var: str):
        super().__init__(name=name, input_var=input_var)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        return {"result": self.input_var}

    def tool_run(self, *args: Any, **kwargs: Any) -> Any:
        return {"tool_result": args[0]}

    async def tool_arun(self, *args: Any, **kwargs: Any) -> Any:
        return {"async_tool_result": args[0]}


class MockAINode(AINode):
    """Mock AI node implementation."""

    input_var: str = Field(description="Input variable for testing")

    def __init__(self, name: str, input_var: str):
        super().__init__(name=name, input_var=input_var)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        return {"messages": {"result": self.input_var}}


def test_decode_variables():
    # Setup
    state = State({"results": {"node1": {"data": {"value": "test_value"}}}})

    # Test node with variable reference
    node = MockTaskNode(name="test", input_var="{{node1.data.value}}")
    node.decode_variables(state)

    assert node.input_var == "test_value"

    # Test node without variable reference
    node = MockTaskNode(name="test", input_var="plain_text")
    node.decode_variables(state)

    assert node.input_var == "plain_text"


@pytest.mark.asyncio
async def test_ai_node_call():
    # Setup
    state = State({"results": {}})
    config = RunnableConfig()
    node = MockAINode(name="test_ai", input_var="test_value")

    # Execute
    result = await node(state, config)

    # Assert
    assert result == {
        "messages": {"result": "test_value"},
        "results": {"test_ai": {"result": "test_value"}},
    }


def test_task_node_tool_run():
    node = MockTaskNode(name="test", input_var="test_value")
    result = node.tool_run("test_arg")
    assert result == {"tool_result": "test_arg"}


@pytest.mark.asyncio
async def test_task_node_tool_arun():
    node = MockTaskNode(name="test", input_var="test_value")
    result = await node.tool_arun("test_arg")
    assert result == {"async_tool_result": "test_arg"}


def test_decode_variables_with_results_prefix():
    """Test that paths starting with 'results' are handled correctly."""
    state = State({"results": {"node1": {"value": "test_from_results"}}})

    node = MockTaskNode(name="test", input_var="{{results.node1.value}}")
    node.decode_variables(state)

    assert node.input_var == "test_from_results"


def test_decode_variables_non_dict_traversal():
    """Test that traversal stops when encountering non-dict values."""
    state = State({"results": {"node1": "simple_string"}})

    # Try to traverse into a string (which should fail and return original)
    node = MockTaskNode(name="test", input_var="{{node1.nested.value}}")
    node.decode_variables(state)

    # Should return the original template string since traversal failed
    assert node.input_var == "{{node1.nested.value}}"


def test_decode_variables_nested_dict():
    """Test decoding nested dictionaries within node attributes."""

    class MockNodeWithDict(TaskNode):
        """Mock node with dict attribute."""

        config: dict[str, Any] = Field(description="Config dictionary")

        async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
            return {"result": self.config}

    state = State({"results": {"prev_node": {"key1": "value1", "key2": "value2"}}})

    node = MockNodeWithDict(
        name="test",
        config={
            "param1": "{{prev_node.key1}}",
            "param2": "{{prev_node.key2}}",
            "static": "unchanged",
        },
    )
    node.decode_variables(state)

    assert node.config == {
        "param1": "value1",
        "param2": "value2",
        "static": "unchanged",
    }


def test_decode_variables_nested_list():
    """Test decoding lists within node attributes."""

    class MockNodeWithList(TaskNode):
        """Mock node with list attribute."""

        items: list[Any] = Field(description="List of items")

        async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
            return {"result": self.items}

    state = State({"results": {"prev_node": {"val1": "a", "val2": "b"}}})

    node = MockNodeWithList(
        name="test",
        items=["{{prev_node.val1}}", "{{prev_node.val2}}", "static_value"],
    )
    node.decode_variables(state)

    assert node.items == ["a", "b", "static_value"]


def test_decode_variables_with_pydantic_model():
    """Test decoding Pydantic model fields."""
    from pydantic import BaseModel

    class InnerModel(BaseModel):
        """Inner Pydantic model."""

        field1: str
        field2: str

    class MockNodeWithModel(TaskNode):
        """Mock node with Pydantic model attribute."""

        model: InnerModel = Field(description="Inner model")

        async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
            return {"result": self.model.model_dump()}

    state = State({"results": {"data": {"x": "decoded_x", "y": "decoded_y"}}})

    inner = InnerModel(field1="{{data.x}}", field2="{{data.y}}")
    node = MockNodeWithModel(name="test", model=inner)
    node.decode_variables(state)

    assert node.model.field1 == "decoded_x"
    assert node.model.field2 == "decoded_y"


@pytest.mark.asyncio
async def test_task_node_call():
    """Test TaskNode __call__ wraps results correctly."""
    state = State({"results": {}})
    config = RunnableConfig()
    node = MockTaskNode(name="test_task", input_var="test_value")

    result = await node(state, config)

    assert result == {"results": {"test_task": {"result": "test_value"}}}


@pytest.mark.asyncio
async def test_base_node_tool_methods_default():
    """Test that base node tool methods have default implementations."""
    from orcheo.nodes.base import BaseNode

    class MinimalNode(BaseNode):
        """Minimal node for testing base methods."""

        pass

    node = MinimalNode(name="minimal")

    # These should not raise errors, just pass through
    assert node.tool_run("arg") is None
    result = await node.tool_arun("arg")
    assert result is None


class MockDecisionNode(DecisionNode):
    """Mock decision node implementation."""

    condition_var: str = Field(description="Variable to check for routing")
    true_path: str = Field(description="Path when condition is true")
    false_path: str = Field(description="Path when condition is false")

    async def run(self, state: State, config: RunnableConfig) -> str | list[Send]:
        if self.condition_var == "true":
            return self.true_path
        return self.false_path


@pytest.mark.asyncio
async def test_decision_node_call_returns_string():
    """Test DecisionNode __call__ returns path string."""
    state = State({"results": {}})
    config = RunnableConfig()
    node = MockDecisionNode(
        name="decision",
        condition_var="true",
        true_path="next_node",
        false_path="other_node",
    )

    result = await node(state, config)

    assert result == "next_node"


@pytest.mark.asyncio
async def test_decision_node_call_with_variable_decoding():
    """Test DecisionNode decodes variables before routing."""
    state = State({"results": {"check": {"status": "true"}}})
    config = RunnableConfig()
    node = MockDecisionNode(
        name="decision",
        condition_var="{{check.status}}",
        true_path="success_node",
        false_path="failure_node",
    )

    result = await node(state, config)

    assert result == "success_node"


class MockDecisionNodeWithSend(DecisionNode):
    """Mock decision node that returns Send list."""

    async def run(self, state: State, config: RunnableConfig) -> str | list[Send]:
        # Return a list of Send for fan-out scenarios
        return [
            Send("branch_a", {"data": "a"}),
            Send("branch_b", {"data": "b"}),
        ]


@pytest.mark.asyncio
async def test_decision_node_call_returns_send_list():
    """Test DecisionNode __call__ can return Send list for fan-out."""
    state = State({"results": {}})
    config = RunnableConfig()
    node = MockDecisionNodeWithSend(name="fan_out")

    result = await node(state, config)

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(item, Send) for item in result)
    assert result[0].node == "branch_a"
    assert result[1].node == "branch_b"
