"""Tests for base node implementation."""

from typing import Any
import pytest
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import AINode, TaskNode


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
