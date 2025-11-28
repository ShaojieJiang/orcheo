import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.edges import While
from orcheo.graph.state import State


@pytest.mark.asyncio
async def test_while_node_iterations_and_limit() -> None:
    state = State({"results": {}})
    node = While(
        name="loop",
        conditions=[{"operator": "less_than", "right": 2}],
        max_iterations=2,
    )

    first = await node(state, RunnableConfig())
    assert first == "continue"

    state["results"]["loop"] = {"iteration": 1}

    second = await node(state, RunnableConfig())
    assert second == "continue"

    state["results"]["loop"] = {"iteration": 2}

    third = await node(state, RunnableConfig())
    assert third == "exit"


def test_while_node_previous_iteration_reads_state() -> None:
    node = While(name="loop")
    state = {"results": {"loop": {"iteration": 5}}}
    assert node._previous_iteration(state) == 5

    empty_state = {"results": {"loop": {"iteration": "x"}}}
    assert node._previous_iteration(empty_state) == 0

    missing_results_state = {}
    assert node._previous_iteration(missing_results_state) == 0


@pytest.mark.asyncio
async def test_while_node_with_or_logic() -> None:
    state = State({"results": {}})
    node = While(
        name="loop",
        conditions=[
            {"operator": "equals", "right": 5},
            {"operator": "less_than", "right": 3},
        ],
        condition_logic="or",
    )

    first = await node(state, RunnableConfig())
    assert first == "continue"


@pytest.mark.asyncio
async def test_while_node_without_max_iterations() -> None:
    state = State({"results": {}})
    node = While(
        name="loop",
        conditions=[{"operator": "less_than", "right": 5}],
    )

    first = await node(state, RunnableConfig())
    assert first == "continue"
