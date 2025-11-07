import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.logic import WhileNode


@pytest.mark.asyncio
async def test_while_node_iterations_and_limit() -> None:
    state = State({"results": {}})
    node = WhileNode(
        name="loop",
        conditions=[{"operator": "less_than", "right": 2}],
        max_iterations=2,
    )

    first = await node(state, RunnableConfig())
    first_payload = first["results"]["loop"]
    assert first_payload["should_continue"] is True
    assert first_payload["iteration"] == 1
    assert first_payload["branch"] == "continue"

    state["results"]["loop"] = first_payload

    second = await node(state, RunnableConfig())
    second_payload = second["results"]["loop"]
    assert second_payload["should_continue"] is True
    assert second_payload["iteration"] == 2

    state["results"]["loop"] = second_payload

    third = await node(state, RunnableConfig())
    third_payload = third["results"]["loop"]
    assert third_payload["should_continue"] is False
    assert third_payload["limit_reached"] is True
    assert third_payload["iteration"] == 2
    assert third_payload["branch"] == "exit"


def test_while_node_previous_iteration_reads_state() -> None:
    node = WhileNode(name="loop")
    state = {"results": {"loop": {"iteration": 5}}}
    assert node._previous_iteration(state) == 5

    empty_state = {"results": {"loop": {"iteration": "x"}}}
    assert node._previous_iteration(empty_state) == 0

    missing_results_state = {}
    assert node._previous_iteration(missing_results_state) == 0


@pytest.mark.asyncio
async def test_while_node_with_or_logic() -> None:
    state = State({"results": {}})
    node = WhileNode(
        name="loop",
        conditions=[
            {"operator": "equals", "right": 5},
            {"operator": "less_than", "right": 3},
        ],
        condition_logic="or",
    )

    first = await node(state, RunnableConfig())
    first_payload = first["results"]["loop"]
    assert first_payload["should_continue"] is True
    assert first_payload["iteration"] == 1
    assert first_payload["condition_logic"] == "or"


@pytest.mark.asyncio
async def test_while_node_without_max_iterations() -> None:
    state = State({"results": {}})
    node = WhileNode(
        name="loop",
        conditions=[{"operator": "less_than", "right": 5}],
    )

    first = await node(state, RunnableConfig())
    first_payload = first["results"]["loop"]
    assert first_payload["should_continue"] is True
    assert first_payload["max_iterations"] is None
    assert first_payload["limit_reached"] is False
