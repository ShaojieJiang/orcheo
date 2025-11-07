import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.logic import SwitchNode


@pytest.mark.asyncio
async def test_switch_node_casefolds_strings() -> None:
    state = State({"results": {}})
    node = SwitchNode(
        name="router",
        value="Completed",
        case_sensitive=False,
        cases=[{"match": "completed", "branch_key": "completed"}],
    )

    result = await node(state, RunnableConfig())
    payload = result["results"]["router"]

    assert payload["branch"] == "completed"
    assert payload["processed"] == "completed"
    assert payload["value"] == "Completed"
    assert payload["cases"][0]["result"] is True


@pytest.mark.asyncio
async def test_switch_node_formats_special_values() -> None:
    state = State({"results": {}})
    node = SwitchNode(
        name="router",
        value=None,
        cases=[{"match": True, "branch_key": "truthy"}],
        default_branch_key="fallback",
    )

    payload = (await node(state, RunnableConfig()))["results"]["router"]
    assert payload["branch"] == "fallback"
    assert payload["cases"][0]["result"] is False


@pytest.mark.asyncio
async def test_switch_node_matches_first_successful_case() -> None:
    state = State({"results": {}})
    node = SwitchNode(
        name="router",
        value="beta",
        cases=[
            {"match": "alpha", "branch_key": "alpha"},
            {"match": "beta", "branch_key": "beta", "label": "Second"},
        ],
    )

    payload = (await node(state, RunnableConfig()))["results"]["router"]
    assert payload["branch"] == "beta"
    assert payload["cases"][1]["result"] is True


@pytest.mark.asyncio
async def test_switch_node_case_sensitive_override() -> None:
    state = State({"results": {}})
    node = SwitchNode(
        name="router",
        value="TEST",
        case_sensitive=False,
        cases=[
            {"match": "wrong", "branch_key": "first"},
            {"match": "test", "branch_key": "second"},
        ],
    )

    result = await node(state, RunnableConfig())
    payload = result["results"]["router"]

    assert payload["branch"] == "second"
    assert payload["cases"][1]["result"] is True
    assert payload["processed"] == "test"
