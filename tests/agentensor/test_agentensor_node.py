"""Tests for AgentensorNode registration and prompt interpolation."""

from __future__ import annotations
from typing import Any, cast
import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.agentensor.prompts import TrainablePrompt
from orcheo.graph.state import State
from orcheo.nodes.agentensor import AgentensorNode
from orcheo.nodes.registry import registry
from orcheo.runtime.runnable_config import RunnableConfigModel


def _build_state_and_config() -> tuple[State, RunnableConfig]:
    base_config = RunnableConfigModel(
        prompts={"seed": TrainablePrompt(text="Hello world")},
        tags=["experiment"],
        run_name="agentensor-eval",
    )
    runtime_config = base_config.to_runnable_config("exec-agentensor")
    state_config = base_config.to_state_config("exec-agentensor")
    state = cast(
        State,
        {
            "inputs": {"lang": "en"},
            "results": {},
            "structured_response": {},
            "config": state_config,
        },
    )
    return state, runtime_config


@pytest.mark.asyncio
async def test_agentensor_node_resolves_prompts_from_config() -> None:
    state, runtime_config = _build_state_and_config()
    node = AgentensorNode(
        name="agentensor",
        prompts={
            "candidate": TrainablePrompt(
                text="{{config.prompts.seed.text}}",
                metadata={"lang": "{{inputs.lang}}"},
                requires_grad=True,
            )
        },
    )

    result = await node(state, runtime_config)

    payload: dict[str, Any] = result["results"]["agentensor"]
    candidate = payload["prompts"]["candidate"]
    assert candidate["text"] == "Hello world"
    assert candidate["metadata"]["lang"] == "en"
    assert payload["tags"] == ["experiment"]
    assert registry.get_node("AgentensorNode") is AgentensorNode
