"""Tests for runnable config validation and merging."""

from __future__ import annotations
import pytest
from orcheo.agentensor.prompts import TrainablePrompt
from orcheo.runtime.runnable_config import RunnableConfigModel, parse_runnable_config


def test_parse_runnable_config_builds_runtime_payload() -> None:
    model = parse_runnable_config(
        {
            "tags": ["A", "a "],
            "metadata": {"foo": "bar"},
            "recursion_limit": 10,
            "prompts": {"welcome": {"text": "hi", "type": "TextTensor"}},
        }
    )

    runtime_config = model.to_runnable_config("exec-1")
    assert runtime_config["configurable"]["thread_id"] == "exec-1"
    assert runtime_config["tags"] == ["A"]
    assert runtime_config["metadata"] == {"foo": "bar"}
    assert runtime_config["recursion_limit"] == 10
    assert runtime_config["prompts"]["welcome"]["text"] == "hi"


def test_state_config_keeps_prompt_models() -> None:
    prompt = TrainablePrompt(text="Hello there", requires_grad=True)
    model = RunnableConfigModel(prompts={"seed": prompt})

    state_config = model.to_state_config("thread-123")

    seed_prompt = state_config["prompts"]["seed"]
    assert isinstance(seed_prompt, TrainablePrompt)
    assert seed_prompt.requires_grad is True
    assert state_config["configurable"]["thread_id"] == "thread-123"


def test_parse_runnable_config_rejects_non_serialisable_metadata() -> None:
    with pytest.raises(ValueError):
        parse_runnable_config({"metadata": {"ts": object()}})


def test_parse_runnable_config_enforces_limits() -> None:
    with pytest.raises(ValueError):
        parse_runnable_config({"recursion_limit": 1000})
    with pytest.raises(ValueError):
        parse_runnable_config({"max_concurrency": 10_000})
