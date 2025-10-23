import asyncio
from typing import cast

import pytest
from langchain_core.runnables import RunnableConfig

from orcheo.graph.state import State
from orcheo.nodes.logic import (
    ComparisonOperator,
    DelayNode,
    IfElseNode,
    SetVariableNode,
    StickyNoteNode,
    SwitchNode,
    WhileNode,
    evaluate_condition,
    _build_nested,
)


@pytest.mark.asyncio
async def test_if_else_contains_and_membership_operations():
    state = State({"results": {}})
    contains_node = IfElseNode(
        name="contains_list",
        left=["alpha", "beta"],
        operator="contains",
        right="beta",
    )
    contains_result = await contains_node(state, RunnableConfig())
    assert contains_result["results"]["contains_list"]["condition"] is True

    not_contains_node = IfElseNode(
        name="no_match",
        left="Signal",
        operator="not_contains",
        right="noise",
        case_sensitive=False,
    )
    not_contains_result = await not_contains_node(state, RunnableConfig())
    assert not_contains_result["results"]["no_match"]["condition"] is True

    in_node = IfElseNode(
        name="key_lookup",
        left="token",
        operator="in",
        right={"token": 1},
    )
    in_result = await in_node(state, RunnableConfig())
    assert in_result["results"]["key_lookup"]["condition"] is True

    not_in_node = IfElseNode(
        name="missing_key",
        left="gamma",
        operator="not_in",
        right={"alpha": 1},
    )
    not_in_result = await not_in_node(state, RunnableConfig())
    assert not_in_result["results"]["missing_key"]["condition"] is True

    invalid_node = IfElseNode(
        name="bad_container",
        left=object(),
        operator="contains",
        right="value",
    )
    with pytest.raises(ValueError):
        await invalid_node(state, RunnableConfig())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("left", "operator", "right", "case_sensitive", "expected"),
    [
        (5, "greater_than", 3, True, True),
        ("Hello", "equals", "hello", True, False),
        ("Hello", "equals", "hello", False, True),
    ],
)
async def test_if_else_node(left, operator, right, case_sensitive, expected):
    state = State({"results": {}})
    node = IfElseNode(
        name="condition",
        left=left,
        operator=operator,
        right=right,
        case_sensitive=case_sensitive,
    )

    result = await node(state, RunnableConfig())
    payload = result["results"]["condition"]

    assert payload["condition"] is expected
    assert payload["branch"] == ("true" if expected else "false")


@pytest.mark.asyncio
async def test_switch_node_casefolds_strings():
    state = State({"results": {}})
    node = SwitchNode(name="router", value="Completed", case_sensitive=False)

    result = await node(state, RunnableConfig())
    payload = result["results"]["router"]

    assert payload["case"] == "completed"
    assert payload["processed"] == "completed"
    assert payload["value"] == "Completed"


@pytest.mark.asyncio
async def test_switch_node_formats_special_values():
    state = State({"results": {}})
    true_node = SwitchNode(name="router_true", value=True)
    true_payload = (await true_node(state, RunnableConfig()))["results"]["router_true"]
    assert true_payload["case"] == "true"

    none_node = SwitchNode(name="router_none", value=None)
    none_payload = (await none_node(state, RunnableConfig()))["results"]["router_none"]
    assert none_payload["case"] == "null"


def test_evaluate_condition_raises_for_unknown_operator():
    with pytest.raises(ValueError):
        evaluate_result = cast(ComparisonOperator, "__invalid__")
        evaluate_condition(
            left=1,
            right=2,
            operator=evaluate_result,
            case_sensitive=True,
        )


@pytest.mark.asyncio
async def test_while_node_iterations_and_limit():
    state = State({"results": {}})
    node = WhileNode(
        name="loop",
        operator="less_than",
        right=2,
        max_iterations=2,
    )

    first = await node(state, RunnableConfig())
    first_payload = first["results"]["loop"]
    assert first_payload["should_continue"] is True
    assert first_payload["iteration"] == 1

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


def test_while_node_previous_iteration_reads_state():
    node = WhileNode(name="loop")
    state = {"results": {"loop": {"iteration": 5}}}
    assert node._previous_iteration(state) == 5

    empty_state = {"results": {"loop": {"iteration": "x"}}}
    assert node._previous_iteration(empty_state) == 0

    missing_results_state = {}
    assert node._previous_iteration(missing_results_state) == 0


@pytest.mark.asyncio
async def test_set_variable_node_builds_nested_assignment():
    state = State({"results": {}})
    node = SetVariableNode(name="assign", target_path="user.name", value="Ada")

    result = await node(state, RunnableConfig())
    payload = result["results"]["assign"]

    assert payload["value"] == "Ada"
    assert payload["assigned"] == {"user": {"name": "Ada"}}


def test_build_nested_validates_paths():
    with pytest.raises(ValueError):
        _build_nested("", "value")

    with pytest.raises(ValueError):
        _build_nested("...", "value")


@pytest.mark.asyncio
async def test_delay_node_sleeps(monkeypatch):
    called_with: list[float] = []

    async def fake_sleep(duration: float) -> None:
        called_with.append(duration)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    state = State({"results": {}})
    node = DelayNode(name="pause", duration_seconds=0.5)

    result = await node(state, RunnableConfig())
    payload = result["results"]["pause"]

    assert called_with == [0.5]
    assert payload["duration_seconds"] == 0.5


@pytest.mark.asyncio
async def test_sticky_note_node_returns_content():
    state = State({"results": {}})
    node = StickyNoteNode(name="note", title="Reminder", body="Review PR")

    result = await node(state, RunnableConfig())
    payload = result["results"]["note"]

    assert payload == {"title": "Reminder", "body": "Review PR"}
