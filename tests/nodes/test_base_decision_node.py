"""DecisionNode behavior tests."""

from __future__ import annotations
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.types import Send
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import DecisionNode


class MockDecisionNode(DecisionNode):
    condition_var: str = Field(description="Variable to check for routing")
    true_path: str = Field(description="Path when condition is true")
    false_path: str = Field(description="Path when condition is false")

    async def run(self, state: State, config: RunnableConfig) -> str | list[Send]:
        if self.condition_var == "true":
            return self.true_path
        return self.false_path


@pytest.mark.asyncio
async def test_decision_node_call_returns_string() -> None:
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
async def test_decision_node_call_with_variable_decoding() -> None:
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
    async def run(self, state: State, config: RunnableConfig) -> str | list[Send]:
        return [
            Send("branch_a", {"data": "a"}),
            Send("branch_b", {"data": "b"}),
        ]


@pytest.mark.asyncio
async def test_decision_node_call_returns_send_list() -> None:
    state = State({"results": {}})
    config = RunnableConfig()
    node = MockDecisionNodeWithSend(name="fan_out")

    result = await node(state, config)

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(item, Send) for item in result)
    assert result[0].node == "branch_a"
    assert result[1].node == "branch_b"
