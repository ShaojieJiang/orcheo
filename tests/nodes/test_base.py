"""Tests for base node implementation."""

from typing import Any
from langchain_core.runnables import RunnableConfig
from aic_flow.graph.state import State
from aic_flow.nodes.base import AINode, TaskNode


class TestNode(TaskNode):
    """Test node implementation."""

    def __init__(self, name: str, input_var: str):
        super().__init__(name=name)
        self.input_var = input_var

    def run(self, state: State) -> dict[str, Any]:
        return {"result": self.input_var}


class TestAINode(AINode):
    """Test AI node implementation."""

    def __init__(self, name: str, input_var: str):
        super().__init__(name=name)
        self.input_var = input_var

    def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        return {"result": self.input_var}


def test_decode_variables():
    # Setup
    state = State({"outputs": {"node1": {"data": {"value": "test_value"}}}})

    # Test node with variable reference
    node = TestNode(name="test", input_var="{{node1.data.value}}")
    node.decode_variables(state)

    assert node.input_var == "test_value"

    # Test node without variable reference
    node = TestNode(name="test", input_var="plain_text")
    node.decode_variables(state)

    assert node.input_var == "plain_text"


def test_ai_node_call():
    # Setup
    state = State({"outputs": {}})
    config = RunnableConfig()
    node = TestAINode(name="test_ai", input_var="test_value")

    # Execute
    result = node(state, config)

    # Assert
    assert result["result"] == "test_value"
    assert result["outputs"]["test_ai"]["result"] == "test_value"
