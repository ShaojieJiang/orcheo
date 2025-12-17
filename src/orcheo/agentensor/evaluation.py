"""Evaluation schemas and helpers for Agentensor."""

from __future__ import annotations
import importlib
import inspect
from dataclasses import dataclass
from functools import partial
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


@dataclass
class EvaluationContext:
    """Context passed to evaluator callables."""

    inputs: dict[str, Any]
    output: Any
    expected_output: Any
    metadata: dict[str, Any]
    duration_ms: float


class EvaluationCase(BaseModel):
    """Single evaluation case containing inputs and optional expectations."""

    model_config = ConfigDict(extra="forbid")

    inputs: dict[str, Any] = Field(default_factory=dict)
    expected_output: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationDataset(BaseModel):
    """Dataset wrapper for evaluation cases."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    cases: list[EvaluationCase] = Field(default_factory=list)

    @field_validator("cases")
    @classmethod
    def _ensure_cases(cls, value: list[EvaluationCase]) -> list[EvaluationCase]:
        if not value:
            msg = "At least one evaluation case is required."
            raise ValueError(msg)
        return value


class EvaluatorDefinition(BaseModel):
    """Reference to an evaluator callable or class."""

    model_config = ConfigDict(extra="forbid")

    id: str
    entrypoint: str
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("entrypoint")
    @classmethod
    def _validate_entrypoint(cls, value: str) -> str:
        if ":" not in value:
            msg = "Entrypoint must be in the form 'module:attribute'."
            raise ValueError(msg)
        return value

    def load(self) -> Any:
        """Materialize the evaluator from the entrypoint string."""
        module_path, attr = self.entrypoint.split(":", 1)
        module = importlib.import_module(module_path)
        target = getattr(module, attr)
        if inspect.isclass(target):
            return target(**self.config) if self.config else target()
        if self.config:
            return partial(target, **self.config)
        return target


class EvaluationRequest(BaseModel):
    """Top-level request payload for an evaluation run."""

    model_config = ConfigDict(extra="forbid")

    dataset: EvaluationDataset
    evaluators: list[EvaluatorDefinition] = Field(default_factory=list)
    max_cases: int | None = Field(default=None, gt=0)


__all__ = [
    "EvaluationCase",
    "EvaluationContext",
    "EvaluationDataset",
    "EvaluationRequest",
    "EvaluatorDefinition",
]
