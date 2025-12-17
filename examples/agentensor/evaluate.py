"""Tasks."""

from __future__ import annotations
import json
from dataclasses import dataclass
from typing import TypedDict
from datasets import load_dataset
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.graph import CompiledGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext
from agentensor.module import AgentModule
from agentensor.tensor import TextTensor
from agentensor.train import Trainer


@dataclass
class GenerationTimeout(Evaluator[str, bool]):
    """The generation took too long."""

    threshold: float = 10.0

    async def evaluate(self, ctx: EvaluatorContext[str, bool]) -> EvaluationReason:
        """Evaluate the time taken to generate the output."""
        return EvaluationReason(
            value=ctx.duration <= self.threshold,
            reason=(
                f"The generation took {ctx.duration} seconds, which is longer "
                f"than the threshold of {self.threshold} seconds."
            ),
        )


@dataclass
class MultiLabelClassificationAccuracy(Evaluator):
    """Classification accuracy evaluator."""

    async def evaluate(self, ctx: EvaluatorContext) -> bool:
        """Evaluate the accuracy of the classification."""
        try:
            output = json.loads(ctx.output.text)
        except json.JSONDecodeError:
            return False
        expected = ctx.expected_output
        return set(output) == set(expected)  # type: ignore[arg-type]


class EvaluateState(TypedDict):
    """State of the graph."""

    output: TextTensor


class ClassificationResults(BaseModel, use_attribute_docstrings=True):
    """Classification result for a data."""

    labels: list[str]
    """labels for this data point."""

    def __str__(self) -> str:
        """Return the string representation of the classification results."""
        return json.dumps(self.labels)


class HFMultiClassClassificationTask:
    """Multi-class classification task from Hugging Face."""

    def __init__(
        self,
        task_repo: str,
        evaluators: list[Evaluator],
        model: BaseChatModel | str = "gpt-4o-mini",
    ) -> None:
        """Initialize the multi-class classification task."""
        self.task_repo = task_repo
        self.evaluators = evaluators
        if isinstance(model, str):
            self.model = init_chat_model(model)
        else:
            self.model = model
        self.dataset = self._prepare_dataset()

    def _prepare_dataset(self) -> dict[str, Dataset]:
        """Return the Pydantic Evals dataset."""
        hf_dataset = load_dataset(self.task_repo, trust_remote_code=True)
        dataset = {}
        for split in hf_dataset.keys():
            cases = []
            for example in hf_dataset[split]:
                cases.append(
                    Case(
                        inputs=TextTensor(
                            f"Title: {example['title']}\nContent: {example['content']}",
                            model=self.model,
                        ),
                        expected_output=example["all_labels"],
                    )
                )
            dataset[split] = Dataset(cases=cases, evaluators=self.evaluators)
        return dataset


class AgentNode(AgentModule):
    """Agent node."""

    @property
    def agent(self) -> CompiledGraph:
        """Get agent instance."""
        return create_react_agent(
            self.llm,
            tools=[],
            prompt=self.system_prompt.text,
            response_format=ClassificationResults,
        )


if __name__ == "__main__":
    model = init_chat_model("llama3.2:1b", model_provider="ollama")
    # model = "gpt-4o-mini"

    task = HFMultiClassClassificationTask(
        task_repo="knowledgator/events_classification_biotech",
        evaluators=[GenerationTimeout(), MultiLabelClassificationAccuracy()],
        model=model,
    )
    graph = StateGraph(EvaluateState)
    graph.add_node(
        "agent",
        AgentNode(
            system_prompt=TextTensor(
                (
                    "Classify the following text into one of the following "
                    "categories: [expanding industry, new initiatives or programs, "
                    "article publication, other]"
                ),
                requires_grad=True,
                model=model,
            ),
            llm=model,
        ),
    )
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    compiled_graph = graph.compile()
    trainer = Trainer(
        compiled_graph,
        train_dataset=task.dataset["train"],
        test_dataset=task.dataset["test"],
    )
    trainer.test(limit_cases=10)
