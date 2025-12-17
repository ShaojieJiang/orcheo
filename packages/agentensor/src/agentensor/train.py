"""Trainer."""

from typing import Any, Literal
from langgraph.graph.state import CompiledStateGraph
from pydantic_evals import Dataset
from pydantic_evals.reporting import EvaluationReport
from agentensor.optim import Optimizer
from agentensor.tensor import TextTensor


CompiledGraph = CompiledStateGraph[Any, Any, Any, Any]


class Trainer:
    """Trainer."""

    def __init__(
        self,
        graph: CompiledGraph,
        graph_recursion_limit: int = 25,
        train_dataset: Dataset[TextTensor, TextTensor, Any] | None = None,
        eval_dataset: Dataset[TextTensor, TextTensor, Any] | None = None,
        test_dataset: Dataset[TextTensor, TextTensor, Any] | None = None,
        optimizer: Optimizer | None = None,
        epochs: int = 10,
        stop_threshold: float = 0.95,
    ):
        """Initialize the trainer."""
        self.graph = graph
        self.graph_recursion_limit = graph_recursion_limit
        self.optimizer = optimizer
        self.epochs = epochs
        self.stop_threshold = stop_threshold
        self.train_dataset = train_dataset
        self.eval_dataset = eval_dataset
        self.test_dataset = test_dataset

    async def forward(self, x: TextTensor) -> TextTensor:
        """Forward the graph."""
        result = await self.graph.ainvoke(
            {"output": x}, {"recursion_limit": self.graph_recursion_limit}
        )
        return result["output"]

    def train(self) -> None:
        """Train the graph."""
        assert self.train_dataset, "Train dataset is required"
        assert self.optimizer, "Optimizer is required"
        for i in range(self.epochs):
            report = self.evaluate("train")
            report.print(
                include_input=True, include_output=True, include_durations=True
            )

            # Backward those failed cases
            for case in report.cases:
                losses = []
                for evaluator in case.assertions.values():
                    if not evaluator.value:
                        assert evaluator.reason
                        losses.append(evaluator.reason)
                if losses:
                    case.output.backward(" ".join(losses))

            self.optimizer.step()
            self.optimizer.zero_grad()

            print(f"Epoch {i + 1}")
            for param in self.optimizer.params:
                print(param.text)  # pragma: no cover
            print()
            performance = report.averages()
            assertions = None if performance is None else performance.assertions
            if assertions is not None and assertions >= self.stop_threshold:
                print("Optimization complete.")
                break

    def evaluate(
        self,
        data_split: Literal["train", "eval", "test"] = "eval",
        limit_cases: int | None = None,
    ) -> EvaluationReport:
        """Evaluate the graph."""
        dataset = getattr(self, f"{data_split}_dataset")
        assert dataset, f"{data_split} dataset is required"
        if limit_cases:  # pragma: no cover
            limited_cases = dataset.cases[:limit_cases]
            dataset = Dataset(cases=limited_cases, evaluators=dataset.evaluators)
        report = dataset.evaluate_sync(self.forward)

        return report

    def test(self, limit_cases: int | None = None) -> None:
        """Test the graph."""
        report = self.evaluate("test", limit_cases=limit_cases)
        report.print(include_input=True, include_output=True, include_durations=True)
