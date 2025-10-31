import pytest
from langchain_core.runnables import RunnableConfig

from orcheo.graph.state import State
from orcheo.nodes.utility import (
    DebugNode,
    JavaScriptSandboxNode,
    PythonSandboxNode,
    SubWorkflowNode,
)


@pytest.mark.asyncio
async def test_python_sandbox_executes_source() -> None:
    """PythonSandboxNode should evaluate code and capture stdout."""

    node = PythonSandboxNode(
        name="python_sandbox",
        source="""
value = bindings_value * 2
print('value', value)
result = value
""",
        bindings={"bindings_value": 21},
        include_locals=True,
    )

    state = State({"results": {}, "inputs": {}})
    payload = (await node(state, RunnableConfig()))["results"]["python_sandbox"]

    assert payload["result"] == 42
    assert payload["stdout"] == ["value 42"]
    assert payload["locals"]["value"] == 42


@pytest.mark.asyncio
async def test_python_sandbox_exposes_state() -> None:
    """PythonSandboxNode should expose state when enabled."""

    node = PythonSandboxNode(
        name="python_sandbox",
        source="result = state['results']['count'] + 5",
        expose_state=True,
    )

    state = State({"results": {"count": 7}})
    payload = (await node(state, RunnableConfig()))["results"]["python_sandbox"]

    assert payload["result"] == 12


@pytest.mark.asyncio
async def test_javascript_sandbox_executes_script() -> None:
    """JavaScriptSandboxNode should evaluate JS and capture console output."""

    node = JavaScriptSandboxNode(
        name="js_sandbox",
        script="""
var doubled = input * 2;
console.log('doubled', doubled);
var result = { value: doubled };
""",
        context={"input": 4},
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["js_sandbox"]

    assert payload["result"] == {"value": 8}
    assert payload["console"] == ["doubled 8"]


@pytest.mark.asyncio
async def test_debug_node_taps_state_path() -> None:
    """DebugNode should tap into nested state values and include snapshots."""

    node = DebugNode(
        name="debug",
        message="Inspect value",
        tap_path="items.1.value",
        include_state=True,
    )

    state = State({"results": {"items": [{"value": 2}, {"value": 5}]}})
    payload = (await node(state, RunnableConfig()))["results"]["debug"]

    assert payload["message"] == "Inspect value"
    assert payload["found"] is True and payload["value"] == 5
    assert payload["state"]["results"]["items"][1]["value"] == 5


@pytest.mark.asyncio
async def test_sub_workflow_node_runs_steps_and_propagates() -> None:
    """SubWorkflowNode should execute configured steps sequentially."""

    node = SubWorkflowNode(
        name="sub",
        steps=[
            {
                "type": "SetVariableNode",
                "name": "initial",
                "variables": {"value": 3},
            },
            {
                "type": "SetVariableNode",
                "name": "derived",
                "variables": {
                    "value": "{{ results.initial.value }}",
                    "extra": 9,
                },
            },
        ],
        include_state=True,
        propagate_to_parent=True,
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["sub"]

    assert payload["result"] == {"value": 3, "extra": 9}
    assert [step["name"] for step in payload["steps"]] == ["initial", "derived"]
    assert state["results"]["derived"] == {"value": 3, "extra": 9}
    assert payload["state"]["results"]["derived"]["extra"] == 9


@pytest.mark.asyncio
async def test_sub_workflow_node_validates_step_configuration() -> None:
    """SubWorkflowNode should validate the supplied steps."""

    node = SubWorkflowNode(
        name="sub",
        steps=[{"name": "invalid"}],
    )

    state = State({"results": {}})
    with pytest.raises(ValueError):
        await node(state, RunnableConfig())
