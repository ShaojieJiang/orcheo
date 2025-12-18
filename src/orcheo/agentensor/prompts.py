"""Pydantic shims for configuring agentensor prompt tensors."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any, Literal
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field
from agentensor.tensor import TextTensor


class TrainablePrompt(BaseModel):
    """Schema for trainable prompt tensors carried in runnable configs."""

    text: str
    requires_grad: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    model_kwargs: dict[str, Any] = Field(default_factory=dict)
    type: Literal["TextTensor"] = "TextTensor"

    def to_tensor(
        self,
        model: str | BaseChatModel | None = None,
    ) -> TextTensor:
        """Return a concrete ``TextTensor`` for runtime consumption."""
        target_model = model if model is not None else "gpt-4o-mini"
        return TextTensor(
            text=self.text,
            requires_grad=self.requires_grad,
            metadata=dict(self.metadata),
            model=target_model,
            model_kwargs=dict(self.model_kwargs),
        )


TrainablePrompts = dict[str, TrainablePrompt]


def build_text_tensors(
    prompts: Mapping[str, TrainablePrompt] | None,
    model: str | BaseChatModel | None = None,
) -> dict[str, TextTensor]:
    """Construct runtime tensors from a mapping of trainable prompt configs."""
    if not prompts:
        return {}
    return {name: prompt.to_tensor(model=model) for name, prompt in prompts.items()}


__all__ = ["TrainablePrompt", "TrainablePrompts", "build_text_tensors"]
