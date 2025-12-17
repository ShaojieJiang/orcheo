"""Tests for AgentensorNode registration and prompt interpolation."""

from __future__ import annotations
from typing import Any, cast
import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.agentensor.evaluation import (
    EvaluationCase,
    EvaluationContext,
    EvaluationDataset,
    EvaluatorDefinition,
)
from orcheo.agentensor.prompts import TrainablePrompt
from orcheo.agentensor.training import OptimizerConfig
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


def evaluation_echo(ctx: EvaluationContext) -> dict[str, Any]:
    """Simple evaluator that checks output mirroring."""
    output = ctx.output if isinstance(ctx.output, dict) else {}
    value = output.get("echo") == ctx.inputs.get("prompt")
    return {"value": value, "reason": "echo match" if value else "mismatch"}


def training_evaluator(ctx: EvaluationContext) -> dict[str, Any]:
    """Evaluator used to drive prompt updates in training mode."""
    output = ctx.output if isinstance(ctx.output, dict) else {}
    candidate = output.get("echo", "")
    passed = "feedback" in str(candidate)
    return {"value": passed, "reason": "needs feedback"}


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


@pytest.mark.asyncio
async def test_agentensor_node_runs_evaluation_with_progress() -> None:
    class DummyGraph:
        async def ainvoke(self, state: State, config: RunnableConfig) -> dict[str, Any]:
            return {"results": {"echo": state["inputs"]["prompt"]}}

    progress_events: list[dict[str, Any]] = []

    async def progress(payload: dict[str, Any]) -> None:
        progress_events.append(payload)

    state, runtime_config = _build_state_and_config()
    node = AgentensorNode(
        name="agentensor",
        mode="evaluate",
        dataset=EvaluationDataset(
            cases=[EvaluationCase(inputs={"prompt": "ping"}, metadata={"idx": 0})]
        ),
        evaluators=[
            EvaluatorDefinition(
                id="echo-check",
                entrypoint="tests.agentensor.test_agentensor_node:evaluation_echo",
            )
        ],
        compiled_graph=DummyGraph(),
        graph_config={},
        state_config=state["config"],
        progress_callback=progress,
    )

    result = await node(state, runtime_config)

    payload: dict[str, Any] = result["results"]["agentensor"]
    assert payload["summary"] == {"echo-check": 1.0}
    assert payload["results"][0]["evaluations"]["echo-check"]["passed"] is True
    assert progress_events[0]["event"] == "evaluation_progress"
    assert progress_events[-1]["event"] == "evaluation_summary"


@pytest.mark.asyncio
async def test_agentensor_training_emits_checkpoints_and_best_config() -> None:
    class TrainingGraph:
        async def ainvoke(self, state: State, config: RunnableConfig) -> dict[str, Any]:
            prompt_obj = state["config"]["prompts"]["candidate"]
            prompt_text = (
                prompt_obj.text if hasattr(prompt_obj, "text") else prompt_obj["text"]
            )
            return {"results": {"echo": prompt_text}}

    progress_events: list[dict[str, Any]] = []

    async def progress(payload: dict[str, Any]) -> None:
        progress_events.append(payload)

    state, runtime_config = _build_state_and_config()
    node = AgentensorNode(
        name="agentensor_trainer",
        mode="train",
        dataset=EvaluationDataset(
            cases=[EvaluationCase(inputs={"prompt": "ping"}, metadata={"idx": 0})]
        ),
        evaluators=[
            EvaluatorDefinition(
                id="echo-pass",
                entrypoint="tests.agentensor.test_agentensor_node:training_evaluator",
            )
        ],
        compiled_graph=TrainingGraph(),
        graph_config={},
        state_config=state["config"],
        progress_callback=progress,
        optimizer=OptimizerConfig(epochs=2, checkpoint_interval=1, max_concurrency=2),
        workflow_id="wf-training",
        prompts={
            "candidate": TrainablePrompt(
                text="{{config.prompts.seed.text}}",
                requires_grad=True,
            )
        },
    )

    result = await node(state, runtime_config)

    payload: dict[str, Any] = result["results"]["agentensor_trainer"]
    assert payload["summary"]["echo-pass"] == 1.0
    assert payload["best_checkpoint"]["workflow_id"] == "wf-training"
    assert len(payload["checkpoints"]) == 2
    assert "feedback" in payload["prompts"]["candidate"]["text"]
    assert any(event["event"] == "training_checkpoint" for event in progress_events)
