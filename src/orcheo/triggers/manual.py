"""Manual trigger request and dispatch utilities."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ManualDispatchValidationError(ValueError):
    """Raised when manual dispatch payloads fail validation."""


@dataclass(slots=True)
class ManualDispatchRun:
    """Resolved manual dispatch entry targeting a workflow version."""

    workflow_version_id: UUID
    input_payload: dict[str, Any]


class ManualDispatchItem(BaseModel):
    """Single run request within a manual dispatch."""

    model_config = ConfigDict(extra="forbid")

    workflow_version_id: UUID | None = Field(
        default=None,
        description=(
            "Optional workflow version identifier. When omitted the latest version "
            "will be used."
        ),
    )
    input_payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Payload supplied as the run's input context.",
    )


class ManualDispatchRequest(BaseModel):
    """Batch of manual run dispatches for a workflow."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: UUID = Field(description="Identifier of the workflow to execute.")
    actor: str = Field(
        default="manual",
        description="Actor recorded in the workflow run audit trail.",
    )
    runs: list[ManualDispatchItem] = Field(
        default_factory=list,
        min_length=1,
        max_length=100,
        description="Collection of run requests to dispatch in order.",
    )
    label: str | None = Field(
        default=None,
        description=(
            "Optional label describing the trigger source. When omitted a sensible "
            "default is derived based on run count."
        ),
    )

    @field_validator("actor")
    @classmethod
    def _normalize_actor(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "actor must be a non-empty string"
            raise ManualDispatchValidationError(msg)
        return normalized

    @field_validator("label")
    @classmethod
    def _normalize_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            msg = "label must not be empty when provided"
            raise ManualDispatchValidationError(msg)
        return normalized

    @model_validator(mode="after")
    def _enforce_run_limit(self) -> ManualDispatchRequest:
        if not self.runs:
            msg = "at least one run must be provided"
            raise ManualDispatchValidationError(msg)
        return self

    def trigger_label(self) -> str:
        """Return the label recorded on dispatched runs."""
        if self.label:
            return self.label
        return "manual" if len(self.runs) == 1 else "manual_batch"

    def resolve_runs(
        self, *, default_workflow_version_id: UUID
    ) -> list[ManualDispatchRun]:
        """Resolve each request against the provided default version."""
        resolved: list[ManualDispatchRun] = []
        for item in self.runs:
            version_id = item.workflow_version_id or default_workflow_version_id
            resolved.append(
                ManualDispatchRun(
                    workflow_version_id=version_id,
                    input_payload=dict(item.input_payload),
                )
            )
        return resolved


__all__ = [
    "ManualDispatchItem",
    "ManualDispatchRequest",
    "ManualDispatchRun",
    "ManualDispatchValidationError",
]
