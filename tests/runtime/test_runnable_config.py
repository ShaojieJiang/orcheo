"""Tests for runnable config validation and merging."""

from __future__ import annotations
import pytest
from orcheo.agentensor.prompts import TrainablePrompt
from orcheo.runtime.runnable_config import (
    RunnableConfigModel,
    merge_runnable_configs,
    parse_runnable_config,
)


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


def test_parse_runnable_config_rejects_non_serialisable_configurable() -> None:
    with pytest.raises(ValueError):
        parse_runnable_config({"configurable": {"foo": object()}})


def test_callbacks_must_be_serialisable() -> None:
    with pytest.raises(ValueError):
        parse_runnable_config({"callbacks": [object()]})


def test_tags_and_run_name_normalise() -> None:
    model = parse_runnable_config({"tags": [" A ", "a", ""], "run_name": "  run "})

    assert model.tags == ["A"]
    assert model.run_name == "run"


def test_prompts_must_be_trainable_prompt() -> None:
    with pytest.raises(ValueError):
        parse_runnable_config({"prompts": {"bad": object()}})


def test_parse_runnable_config_returns_existing_model() -> None:
    existing = RunnableConfigModel(tags=["keep"])
    parsed = parse_runnable_config(existing)

    assert parsed is existing


def test_json_config_serialises_prompts() -> None:
    prompt = TrainablePrompt(text="Hello", requires_grad=True)
    model = RunnableConfigModel(prompts={"seed": prompt})

    snapshot = model.to_json_config("thread-1")

    assert isinstance(snapshot["prompts"]["seed"], dict)
    assert snapshot["prompts"]["seed"]["text"] == "Hello"


def test_runnable_config_includes_callbacks_and_concurrency_limits() -> None:
    prompt = TrainablePrompt(text="Hello", requires_grad=True)
    model = RunnableConfigModel(
        callbacks=[{"event": "hook"}],
        max_concurrency=6,
        recursion_limit=3,
        prompts={"seed": prompt},
    )

    runtime = model.to_runnable_config("exec-2")
    assert runtime["callbacks"] == [{"event": "hook"}]
    assert runtime["max_concurrency"] == 6

    state_config = model.to_state_config("exec-2")
    assert state_config["recursion_limit"] == 3
    assert state_config["max_concurrency"] == 6


def test_run_name_none_remains_none() -> None:
    model = RunnableConfigModel(run_name=None)

    assert model.run_name is None


def test_validate_prompts_accepts_none() -> None:
    assert RunnableConfigModel._validate_prompts(None) is None


def test_validate_prompts_rejects_non_trainable_prompt_dict() -> None:
    with pytest.raises(ValueError, match="must be a TrainablePrompt"):
        RunnableConfigModel._validate_prompts({"bad": object()})


def test_merge_runnable_configs_combines_overrides_and_base_prompts() -> None:
    base = {
        "configurable": {"thread_id": "keep", "base": "value"},
        "metadata": {"team": "ops"},
        "prompts": {"seed": TrainablePrompt(text="base")},
        "tags": ["stable"],
    }
    override = {
        "configurable": {"override": "value"},
        "metadata": {"team": "override"},
        "prompts": {"extra": TrainablePrompt(text="override")},
        "tags": ["latest"],
    }

    merged = merge_runnable_configs(base, override)

    assert merged.configurable["base"] == "value"
    assert merged.configurable["override"] == "value"
    assert merged.metadata == {"team": "override"}
    assert set(merged.prompts.keys()) == {"seed", "extra"}
    assert merged.prompts["seed"].text == "base"
    assert merged.prompts["extra"].text == "override"
    assert merged.tags == ["latest"]


def test_merge_runnable_configs_clears_empty_mappings() -> None:
    base = {"metadata": {"team": "ops"}}
    override = {"metadata": {}}

    merged = merge_runnable_configs(base, override)

    assert merged.metadata == {}


def test_merge_runnable_configs_resets_prompts_when_override_null() -> None:
    base = {"prompts": {"seed": TrainablePrompt(text="keep")}}
    override = {"prompts": None}

    merged = merge_runnable_configs(base, override)

    assert merged.prompts is None
