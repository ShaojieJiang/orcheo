"""Training payload schemas for AgentensorNode."""

from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field
from orcheo.agentensor.evaluation import EvaluationDataset, EvaluatorDefinition


_MAX_EPOCHS = 50
_MAX_CHECKPOINT_INTERVAL = 100
_MAX_CASE_TIMEOUT = 300
_MAX_TRAIN_CONCURRENCY = 16


class OptimizerConfig(BaseModel):
    """Configuration for the training optimizer loop."""

    model_config = ConfigDict(extra="forbid")

    epochs: int = Field(default=3, ge=1, le=_MAX_EPOCHS)
    checkpoint_interval: int = Field(default=1, ge=1, le=_MAX_CHECKPOINT_INTERVAL)
    case_timeout_seconds: int = Field(default=30, ge=1, le=_MAX_CASE_TIMEOUT)
    max_concurrency: int = Field(default=4, ge=1, le=_MAX_TRAIN_CONCURRENCY)


class TrainingRequest(BaseModel):
    """Top-level request payload for a training run."""

    model_config = ConfigDict(extra="forbid")

    dataset: EvaluationDataset
    evaluators: list[EvaluatorDefinition] = Field(default_factory=list)
    optimizer: OptimizerConfig = Field(default_factory=OptimizerConfig)
    max_cases: int | None = Field(default=None, gt=0)


__all__ = ["OptimizerConfig", "TrainingRequest"]
