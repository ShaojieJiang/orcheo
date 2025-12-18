"""Agentensor training example using Orcheo integration."""

from __future__ import annotations
import asyncio
import uuid
from dataclasses import dataclass
from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic_evals.evaluators.common import LLMJudge
from pydantic_evals.evaluators.llm_as_a_judge import judge_input_output, judge_output
from orcheo.agentensor.evaluation import (
    EvaluationCase,
    EvaluationContext,
    EvaluationDataset,
    EvaluatorDefinition,
)
from orcheo.agentensor.prompts import TrainablePrompt
from orcheo.agentensor.training import OptimizerConfig, TrainingRequest
from orcheo.graph.state import State
from orcheo.nodes.agentensor import AgentensorNode
from orcheo.nodes.base import TaskNode
from orcheo.runtime.credentials import CredentialResolver, credential_resolution
from orcheo.runtime.runnable_config import RunnableConfigModel


NODE_NAME = "prompt_echo"


class PromptEchoNode(TaskNode):
    """Echo the configured prompt alongside the user input."""

    prompt_text: TrainablePrompt | str
    input_text: str

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the combined prompt and input text."""
        prompt = self.prompt_text
        prompt_text = (
            prompt.text if isinstance(prompt, TrainablePrompt) else str(prompt)
        )
        reply = f"{prompt_text} {self.input_text}".strip()
        return {"reply": reply}


@dataclass
class ChineseLanguageJudge(LLMJudge):
    """Judge whether replies are written in Chinese."""

    rubric: str = "The output should be in Chinese."
    include_input: bool = True

    async def evaluate(self, context: EvaluationContext) -> dict[str, Any]:
        """Score whether the reply matches the Chinese-language rubric."""
        output = context.output if isinstance(context.output, dict) else {}
        node_output = output.get(NODE_NAME, {})
        reply = str(node_output.get("reply", ""))
        if self.include_input:
            grading_output = await judge_input_output(
                context.inputs, reply, self.rubric, self.model, self.model_settings
            )
        else:
            grading_output = await judge_output(
                reply, self.rubric, self.model, self.model_settings
            )
        return {"value": grading_output.pass_, "reason": grading_output.reason}


def build_graph() -> StateGraph:
    """Construct the demo workflow graph."""
    graph = StateGraph(State)
    graph.add_node(
        NODE_NAME,
        PromptEchoNode(
            name=NODE_NAME,
            prompt_text="{{config.prompts.greeter}}",
            input_text="{{inputs.message}}",
        ),
    )
    graph.add_edge(START, NODE_NAME)
    graph.add_edge(NODE_NAME, END)
    return graph


def setup_credentials() -> CredentialResolver:
    """Return a credential resolver connected to the local vault."""
    from orcheo_backend.app.dependencies import get_vault

    vault = get_vault()
    return CredentialResolver(vault)


async def run_training() -> None:
    """Run the Agentensor training loop locally.

    Requires an ``openai_api_key`` credential in the local vault.
    """
    execution_id = f"agentensor-train-{uuid.uuid4()}"
    runnable_config = RunnableConfigModel(
        run_name="agentensor-train-demo",
        tags=["agentensor", "training"],
        metadata={"experiment": "agentensor-train"},
        prompts={
            "greeter": TrainablePrompt(
                text="You are a helpful assistant.",
                requires_grad=True,
                metadata={"locale": "en-US"},
                model_kwargs={"api_key": "[[openai_api_key]]"},
            )
        },
    )
    runtime_config = runnable_config.to_runnable_config(execution_id)
    state_config = runnable_config.to_state_config(execution_id)

    training_request = TrainingRequest(
        dataset=EvaluationDataset(
            id="demo-train-dataset",
            cases=[
                EvaluationCase(inputs={"message": "Hello there!"}),
                EvaluationCase(inputs={"message": "Good morning!"}),
            ],
        ),
        evaluators=[
            EvaluatorDefinition(
                id="chinese-language",
                entrypoint="__main__:ChineseLanguageJudge",
            )
        ],
        optimizer=OptimizerConfig(epochs=2, checkpoint_interval=1, max_concurrency=2),
    )

    compiled_graph = build_graph().compile()

    node: AgentensorNode | None = None

    async def on_progress(payload: dict[str, Any]) -> None:
        event = payload.get("event", "unknown")
        print(f"[progress] {event}: {payload.get('payload', {})}")
        if event == "training_epoch_complete" and node is not None:
            for name, prompt in (node.prompts or {}).items():
                if getattr(prompt, "requires_grad", False):
                    print(f"[prompt] {name}: {prompt.text}")

    node = AgentensorNode(
        name="agentensor_train",
        mode="train",
        prompts=runnable_config.prompts or {},
        dataset=training_request.dataset,
        evaluators=training_request.evaluators,
        max_cases=training_request.max_cases,
        optimizer=training_request.optimizer,
        compiled_graph=compiled_graph,
        graph_config={},
        state_config=state_config,
        progress_callback=on_progress,
        workflow_id="wf-agentensor-demo",
    )

    state: State = {
        "inputs": {},
        "messages": [],
        "results": {},
        "structured_response": None,
        "config": state_config,
    }

    resolver = setup_credentials()
    with credential_resolution(resolver):
        result = await node(state, runtime_config)
    payload = result["results"][node.name]
    print("\nSummary:", payload["summary"])
    print("Best checkpoint:", payload.get("best_checkpoint"))


def main() -> None:
    """Entrypoint for the training example."""
    asyncio.run(run_training())


if __name__ == "__main__":
    main()
