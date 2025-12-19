"""Tests for evaluation schema helpers."""

from __future__ import annotations
from typing import Any
import pytest
from orcheo.agentensor.evaluation import (
    EvaluationContext,
    EvaluationDataset,
    EvaluatorDefinition,
)


class SampleEvaluator:
    def __init__(self, prefix: str = "default") -> None:
        self.prefix = prefix

    def __call__(self, ctx: EvaluationContext) -> dict[str, Any]:
        return {"result": f"{self.prefix}:{ctx.output}"}


def sample_evaluator_function(
    ctx: EvaluationContext, *, suffix: str = ""
) -> dict[str, Any]:
    return {"suffix": suffix, "output": ctx.output}


def make_context() -> EvaluationContext:
    return EvaluationContext(
        inputs={"value": 1},
        output="done",
        expected_output="done",
        metadata={},
        duration_ms=1.0,
    )


def test_evaluation_dataset_requires_cases() -> None:
    with pytest.raises(ValueError, match="At least one evaluation case is required"):
        EvaluationDataset(id="test", cases=[])


def test_evaluator_definition_entrypoint_validation() -> None:
    with pytest.raises(ValueError, match="Entrypoint must be in the form"):
        EvaluatorDefinition(id="test", entrypoint="invalid_entrypoint")


def test_evaluator_definition_loads_class() -> None:
    definition = EvaluatorDefinition(
        id="class",
        entrypoint=f"{__name__}:SampleEvaluator",
        config={"prefix": "run"},
    )

    evaluator = definition.load()
    assert isinstance(evaluator, SampleEvaluator)
    assert evaluator(make_context()) == {"result": "run:done"}


def test_evaluator_definition_loads_callable_with_config() -> None:
    definition = EvaluatorDefinition(
        id="function",
        entrypoint=f"{__name__}:sample_evaluator_function",
        config={"suffix": "ok"},
    )

    evaluator = definition.load()
    assert callable(evaluator)
    assert evaluator(make_context()) == {"suffix": "ok", "output": "done"}
