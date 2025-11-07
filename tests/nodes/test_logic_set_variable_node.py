from collections import OrderedDict
import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.logic import SetVariableNode


@pytest.mark.asyncio
async def test_set_variable_node_stores_multiple_variables() -> None:
    state = State({"results": {}})
    node = SetVariableNode(
        name="assign",
        variables={
            "user_name": "Ada",
            "user_age": 30,
            "user_active": True,
            "user_tags": ["admin", "developer"],
        },
    )

    result = await node(state, RunnableConfig())
    payload = result["results"]["assign"]

    assert payload == {
        "user_name": "Ada",
        "user_age": 30,
        "user_active": True,
        "user_tags": ["admin", "developer"],
    }


@pytest.mark.asyncio
async def test_set_variable_node_handles_nested_dicts() -> None:
    state = State({"results": {}})
    node = SetVariableNode(
        name="assign",
        variables={
            "user": {"name": "Ada", "role": "admin"},
            "settings": {"theme": "dark", "notifications": True},
        },
    )

    result = await node(state, RunnableConfig())
    payload = result["results"]["assign"]

    assert payload["user"]["name"] == "Ada"
    assert payload["settings"]["theme"] == "dark"


@pytest.mark.asyncio
async def test_set_variable_node_supports_dotted_paths() -> None:
    state = State({"results": {}})
    node = SetVariableNode(
        name="assign",
        variables={
            "profile": {"role": "builder"},
            "profile.name": "Ada",
            "profile.stats.score": 42,
            "flags.is_active": True,
        },
    )

    result = await node(state, RunnableConfig())
    payload = result["results"]["assign"]

    assert payload["profile"]["role"] == "builder"
    assert payload["profile"]["name"] == "Ada"
    assert payload["profile"]["stats"]["score"] == 42
    assert payload["flags"]["is_active"] is True


@pytest.mark.asyncio
async def test_set_variable_node_merges_existing_dicts() -> None:
    state = State({"results": {}})
    node = SetVariableNode(
        name="assign",
        variables=OrderedDict(
            [
                ("profile.name", "Ada"),
                ("profile", {"role": "builder"}),
            ]
        ),
    )

    result = await node(state, RunnableConfig())
    payload = result["results"]["assign"]

    assert payload["profile"]["name"] == "Ada"
    assert payload["profile"]["role"] == "builder"


@pytest.mark.asyncio
async def test_set_variable_node_empty_variables() -> None:
    state = State({"results": {}})
    node = SetVariableNode(name="assign", variables={})

    result = await node(state, RunnableConfig())
    payload = result["results"]["assign"]

    assert payload == {}
