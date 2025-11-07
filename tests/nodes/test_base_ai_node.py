"""Tests for AI node behavior."""

from __future__ import annotations
import pytest
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import AINode


class MockAINode(AINode):
    input_var: str = Field(description="Input variable for testing")

    def __init__(self, name: str, input_var: str):
        super().__init__(name=name, input_var=input_var)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, str]:
        return {"messages": {"result": self.input_var}}  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_ai_node_call() -> None:
    state = State({"results": {}})
    config = RunnableConfig()
    node = MockAINode(name="test_ai", input_var="test_value")

    result = await node(state, config)

    assert result == {"messages": {"result": "test_value"}}
