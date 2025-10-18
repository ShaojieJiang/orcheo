from __future__ import annotations

import asyncio

import pytest

from orcheo.graph.state import State
from orcheo.nodes.logic import (
    Debug,
    Delay,
    GuardrailRule,
    Guardrails,
    IfElse,
    MergeDictionaries,
    SetVariable,
    SubWorkflow,
    Switch,
)


@pytest.mark.asyncio()
async def test_set_variable_node() -> None:
    node = SetVariable(name="greeting", value="hello")
    state = State({"results": {}})
    output = await node(state, None)
    assert output["results"]["greeting"] == "hello"


@pytest.mark.asyncio()
async def test_merge_dictionaries_node() -> None:
    state = State({"results": {"a": {"x": 1}, "b": {"y": 2}}})
    node = MergeDictionaries(name="merged", sources=["a", "b"])
    output = await node(state, None)
    assert output["results"]["merged"] == {"x": 1, "y": 2}


@pytest.mark.asyncio()
async def test_if_else_switch_nodes() -> None:
    state = State({"results": {}})
    if_node = IfElse(
        name="branch",
        condition=True,
        true_payload={"result": 1},
        false_payload={"result": 0},
    )
    switch_node = Switch(
        name="switch", value="beta", cases={"alpha": 1, "beta": 2}, default=0
    )

    if_output = await if_node(state, None)
    switch_output = await switch_node(state, None)

    assert if_output["results"]["branch"] == {"result": 1}
    assert switch_output["results"]["switch"] == 2


@pytest.mark.asyncio()
async def test_delay_and_debug_nodes() -> None:
    state = State({"results": {}})
    delay = Delay(name="pause", seconds=0.01)
    debug = Debug(name="inspect", message="testing", include_results=True)

    start = asyncio.get_event_loop().time()
    await delay(state, None)
    duration = asyncio.get_event_loop().time() - start
    assert duration >= 0.01

    debug_output = await debug(state, None)
    assert debug_output["results"]["inspect"]["message"] == "testing"


@pytest.mark.asyncio()
async def test_guardrails_pass_and_fail() -> None:
    state = State({"results": {"prompt": "short", "score": 5}})
    guardrails = Guardrails(
        name="validate",
        rules=[
            GuardrailRule(name="PromptLength", path=["prompt"], max_length=10),
            GuardrailRule(name="Score", path=["score"], allowed_values=[5, 6]),
        ],
    )
    output = await guardrails(state, None)
    assert output["results"]["validate"]["status"] == "passed"

    failing = Guardrails(
        name="validate",
        rules=[GuardrailRule(name="PromptLength", path=["prompt"], max_length=2)],
    )
    with pytest.raises(ValueError):
        await failing(state, None)


@pytest.mark.asyncio()
async def test_subworkflow_executes_steps() -> None:
    state = State({"results": {}})
    step_one = SetVariable(name="step_one", value=1)
    step_two = SetVariable(name="step_two", value=2)
    subworkflow = SubWorkflow(name="sub", steps=[step_one, step_two])

    output = await subworkflow(state, None)
    assert output["results"]["sub"] == {"step_one": 1, "step_two": 2}
