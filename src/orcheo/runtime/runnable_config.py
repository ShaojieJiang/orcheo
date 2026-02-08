"""Utilities for validating and merging ``RunnableConfig`` payloads."""

from __future__ import annotations
import json
from collections.abc import Mapping
from typing import Any, cast
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from orcheo.agentensor.prompts import TrainablePrompt, TrainablePrompts


# Conservative limits to guard against runaway graphs.
_MAX_RECURSION_LIMIT = 250
_MAX_CONCURRENCY = 32


def _ensure_json_serialisable(value: Any, *, field_name: str) -> Any:
    """Raise a validation error when the value cannot be JSON-serialised."""
    try:
        json.dumps(value)
    except TypeError as exc:
        msg = f"{field_name} must be JSON serialisable"
        raise ValueError(msg) from exc
    return value


class RunnableConfigModel(BaseModel):
    """Validated representation of a user-supplied ``RunnableConfig``."""

    model_config = ConfigDict(extra="forbid")

    configurable: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    callbacks: list[Any] = Field(default_factory=list)
    run_name: str | None = None
    recursion_limit: int | None = Field(
        default=None,
        ge=1,
        le=_MAX_RECURSION_LIMIT,
        description="Maximum recursion depth allowed for the graph.",
    )
    max_concurrency: int | None = Field(
        default=None,
        ge=1,
        le=_MAX_CONCURRENCY,
        description="Maximum concurrent tasks allowed for the graph.",
    )
    prompts: TrainablePrompts | None = None

    @field_validator("configurable", "metadata")
    @classmethod
    def _validate_serialisable_mapping(
        cls, value: dict[str, Any], info: ValidationInfo
    ) -> dict[str, Any]:
        field_name = info.field_name or "field"
        _ensure_json_serialisable(value, field_name=field_name)
        return value

    @field_validator("callbacks")
    @classmethod
    def _validate_callbacks(cls, value: list[Any]) -> list[Any]:
        _ensure_json_serialisable(value, field_name="callbacks")
        return value

    @field_validator("tags", mode="after")
    @classmethod
    def _normalise_tags(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for tag in value:
            normalized = tag.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(normalized)
        return deduped

    @field_validator("run_name")
    @classmethod
    def _normalise_run_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        return candidate or None

    @field_validator("prompts", mode="after")
    @classmethod
    def _validate_prompts(
        cls, prompts: TrainablePrompts | None
    ) -> TrainablePrompts | None:
        if prompts is None:
            return None
        for name, prompt in prompts.items():
            if not isinstance(prompt, TrainablePrompt):
                msg = f"Prompt '{name}' must be a TrainablePrompt."
                raise ValueError(msg)
        return prompts

    def to_runnable_config(self, execution_id: str) -> RunnableConfig:
        """Return a LangChain-compatible config merged with runtime defaults."""
        configurable = dict(self.configurable)
        configurable["thread_id"] = execution_id

        config: dict[str, Any] = {"configurable": configurable}
        if self.tags:
            config["tags"] = list(self.tags)
        if self.metadata:
            config["metadata"] = dict(self.metadata)
        if self.callbacks:
            config["callbacks"] = list(self.callbacks)
        if self.run_name is not None:
            config["run_name"] = self.run_name
        if self.recursion_limit is not None:
            config["recursion_limit"] = self.recursion_limit
        if self.max_concurrency is not None:
            config["max_concurrency"] = self.max_concurrency
        if self.prompts:
            config["prompts"] = {
                name: prompt.model_dump(mode="json")
                for name, prompt in self.prompts.items()
            }
        return cast(RunnableConfig, config)

    def to_state_config(self, execution_id: str) -> dict[str, Any]:
        """Return a dict suitable for injecting into runtime state."""
        configurable = dict(self.configurable)
        configurable["thread_id"] = execution_id
        state_config: dict[str, Any] = {
            "configurable": configurable,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "callbacks": list(self.callbacks),
            "run_name": self.run_name,
        }
        if self.recursion_limit is not None:
            state_config["recursion_limit"] = self.recursion_limit
        if self.max_concurrency is not None:
            state_config["max_concurrency"] = self.max_concurrency
        if self.prompts:
            state_config["prompts"] = {
                name: prompt.model_copy(deep=True)
                for name, prompt in self.prompts.items()
            }
        return state_config

    def to_json_config(self, execution_id: str) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot of the merged config."""
        state_config = self.to_state_config(execution_id)
        serialized = {}
        for key, value in state_config.items():
            if key == "prompts" and isinstance(value, Mapping):
                serialized[key] = {
                    name: prompt.model_dump(mode="json")
                    for name, prompt in value.items()
                }
            else:
                serialized[key] = value
        return serialized


def parse_runnable_config(
    value: Mapping[str, Any] | RunnableConfigModel | None,
) -> RunnableConfigModel:
    """Parse and validate a runnable config value."""
    if value is None:
        return RunnableConfigModel()
    if isinstance(value, RunnableConfigModel):
        return value
    return RunnableConfigModel.model_validate(value)


def merge_runnable_configs(
    stored: Mapping[str, Any] | RunnableConfigModel | None,
    override: Mapping[str, Any] | RunnableConfigModel | None,
) -> RunnableConfigModel:
    """Merge stored and override configs, letting override fields win."""
    base = parse_runnable_config(stored)
    if override is None:
        return base
    override_model = (
        override
        if isinstance(override, RunnableConfigModel)
        else RunnableConfigModel.model_validate(override)
    )
    if not override_model.model_fields_set:
        return base  # pragma: no cover

    merged = base.model_dump(mode="python")
    fields_set = override_model.model_fields_set

    if "configurable" in fields_set:
        _merge_mapping_field(merged, base, override_model, "configurable")
    if "metadata" in fields_set:
        _merge_mapping_field(merged, base, override_model, "metadata")
    if "prompts" in fields_set:
        _merge_prompts_field(merged, base, override_model)

    for field in (
        "tags",
        "callbacks",
        "run_name",
        "recursion_limit",
        "max_concurrency",
    ):
        if field in fields_set:
            value = getattr(override_model, field)
            merged[field] = list(value) if isinstance(value, list) else value

    return RunnableConfigModel.model_validate(merged)


def _merge_mapping_field(
    merged: dict[str, Any],
    base: RunnableConfigModel,
    override: RunnableConfigModel,
    field_name: str,
) -> None:
    override_value = dict(getattr(override, field_name))
    if override_value:
        base_value = dict(getattr(base, field_name))
        merged[field_name] = {**base_value, **override_value}
    else:
        merged[field_name] = {}


def _merge_prompts_field(
    merged: dict[str, Any],
    base: RunnableConfigModel,
    override: RunnableConfigModel,
) -> None:
    override_prompts = override.prompts
    if override_prompts is None:
        merged["prompts"] = None
        return
    base_prompts = base.prompts or {}
    merged_prompts = dict(base_prompts)
    merged_prompts.update(override_prompts)
    merged["prompts"] = merged_prompts


__all__ = [
    "RunnableConfigModel",
    "merge_runnable_configs",
    "parse_runnable_config",
]
