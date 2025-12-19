"""Prompt handling tests for the AgentNode."""

from __future__ import annotations
from types import SimpleNamespace
import pytest
from agentensor.tensor import TextTensor
from orcheo.nodes.ai import AgentNode


@pytest.fixture(autouse=True)
def _patch_agentensor_tensor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "agentensor.tensor.init_chat_model", lambda *_, **__: SimpleNamespace()
    )


def test_model_post_init_converts_prompt_for_compound_model() -> None:
    node = AgentNode(
        name="agent",
        ai_model="provider:model",
        system_prompt="Basic prompt",
        model_kwargs={"foo": "bar", "model_provider": "provider"},
    )

    node.model_post_init({})

    assert isinstance(node.system_prompt, TextTensor)
    assert node.system_prompt.text == "Basic prompt"


def test_model_post_init_skips_template_prompt() -> None:
    node = AgentNode(name="agent", ai_model="provider:model", system_prompt="{{value}}")

    node.model_post_init({})

    assert isinstance(node.system_prompt, str)
    assert node.system_prompt == "{{value}}"


def test_get_params_returns_trainable_tensor_when_grad_enabled() -> None:
    node = AgentNode(name="agent", ai_model="provider:model")
    node.system_prompt = TextTensor(
        text="train", requires_grad=True, model=SimpleNamespace()
    )

    params = node.get_params()

    assert len(params) == 1
    assert params[0] is node.system_prompt


def test_get_params_skips_non_trainable_system_prompt() -> None:
    node = AgentNode(name="agent", ai_model="provider:model")
    node.system_prompt = TextTensor(
        text="frozen", requires_grad=False, model=SimpleNamespace()
    )

    assert node.get_params() == []
