"""Tests covering TaskNode behavior and variable decoding."""

from __future__ import annotations
from typing import Any
import pytest
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode


class MockTaskNode(TaskNode):
    """Mock task node used in multiple tests."""

    input_var: str = Field(description="Input variable for testing")

    def __init__(self, name: str, input_var: str):
        super().__init__(name=name, input_var=input_var)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        return {"result": self.input_var}

    def tool_run(self, *args: Any, **kwargs: Any) -> Any:
        return {"tool_result": args[0]}

    async def tool_arun(self, *args: Any, **kwargs: Any) -> Any:
        return {"async_tool_result": args[0]}


def test_decode_variables() -> None:
    state = State({"results": {"node1": {"data": {"value": "test_value"}}}})
    node = MockTaskNode(name="test", input_var="{{node1.data.value}}")
    node.decode_variables(state)
    assert node.input_var == "test_value"

    node = MockTaskNode(name="test", input_var="plain_text")
    node.decode_variables(state)
    assert node.input_var == "plain_text"


def test_decode_variables_with_results_prefix() -> None:
    state = State({"results": {"node1": {"value": "test_from_results"}}})
    node = MockTaskNode(name="test", input_var="{{results.node1.value}}")
    node.decode_variables(state)
    assert node.input_var == "test_from_results"


def test_decode_variables_reads_config_state() -> None:
    state = State({"results": {}, "config": {"threshold": 0.75}})
    node = MockTaskNode(name="test", input_var="{{config.threshold}}")

    node.decode_variables(state)

    assert node.input_var == 0.75


def test_decode_variables_injects_config_argument() -> None:
    state = State({"results": {}})
    node = MockTaskNode(name="test", input_var="{{config.limit}}")

    node.decode_variables(state, config={"limit": 5})

    assert node.input_var == 5
    assert state["config"]["limit"] == 5


def test_decode_variables_non_dict_traversal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    state = State({"results": {"node1": "simple_string"}})
    node = MockTaskNode(name="test", input_var="{{node1.nested.value}}")
    with caplog.at_level("WARNING"):
        node.decode_variables(state)
    assert node.input_var == "{{node1.nested.value}}"
    assert any(
        "could not resolve template" in message.lower()
        for _, _, message in caplog.record_tuples
    )


def test_decode_variables_nested_dict() -> None:
    class MockNodeWithDict(TaskNode):
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


def test_decode_variables_nested_list() -> None:
    class MockNodeWithList(TaskNode):
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


def test_decode_variables_with_pydantic_model() -> None:
    from pydantic import BaseModel

    class InnerModel(BaseModel):
        field1: str
        field2: str

    class MockNodeWithModel(TaskNode):
        model: InnerModel = Field(description="Inner model")

        async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
            return {"result": self.model.model_dump()}

    state = State({"results": {"data": {"x": "decoded_x", "y": "decoded_y"}}})

    inner = InnerModel(field1="{{data.x}}", field2="{{data.y}}")
    node = MockNodeWithModel(name="test", model=inner)
    node.decode_variables(state)

    assert node.model.field1 == "decoded_x"
    assert node.model.field2 == "decoded_y"


def test_task_node_tool_run() -> None:
    node = MockTaskNode(name="test", input_var="test_value")
    result = node.tool_run("test_arg")
    assert result == {"tool_result": "test_arg"}


@pytest.mark.asyncio
async def test_task_node_tool_arun() -> None:
    node = MockTaskNode(name="test", input_var="test_value")
    result = await node.tool_arun("test_arg")
    assert result == {"async_tool_result": "test_arg"}


@pytest.mark.asyncio
async def test_task_node_call() -> None:
    state = State({"results": {}})
    config = RunnableConfig()
    node = MockTaskNode(name="test_task", input_var="test_value")

    result = await node(state, config)
    assert result == {"results": {"test_task": {"result": "test_value"}}}
