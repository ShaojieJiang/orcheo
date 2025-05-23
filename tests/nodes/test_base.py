"""Tests for base node implementation."""

from typing import Any
import pytest
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from aic_flow.graph.state import State
from aic_flow.nodes.base import AINode, TaskNode


class MockTaskNode(TaskNode):
    """Mock task node implementation."""

    input_var: str = Field(description="Input variable for testing")

    def __init__(self, name: str, input_var: str):
        super().__init__(name=name, input_var=input_var)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        return {"result": self.input_var}


class MockAINode(AINode):
    """Mock AI node implementation."""

    input_var: str = Field(description="Input variable for testing")

    def __init__(self, name: str, input_var: str):
        super().__init__(name=name, input_var=input_var)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        return {"result": self.input_var}


def test_decode_variables():
    # Setup
    state = State({"outputs": {"node1": {"data": {"value": "test_value"}}}})

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
    state = State({"outputs": {}})
    config = RunnableConfig()
    node = MockAINode(name="test_ai", input_var="test_value")

    # Execute
    result = await node(state, config)

    # Assert
    assert result["outputs"]["test_ai"]["result"] == "test_value"
