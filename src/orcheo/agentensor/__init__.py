"""Integration helpers for the vendored agentensor package."""

from orcheo.agentensor.prompts import (
    TrainablePrompt,
    TrainablePrompts,
    build_text_tensors,
)


__all__ = ["TrainablePrompt", "TrainablePrompts", "build_text_tensors"]
