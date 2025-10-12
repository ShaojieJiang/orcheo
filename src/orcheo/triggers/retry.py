"""Retry policy configuration and scheduling helpers for trigger runs."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from random import Random
from pydantic import BaseModel, ConfigDict, Field


class RetryPolicyValidationError(ValueError):
    """Raised when retry policy configuration cannot be validated."""


class RetryPolicyConfig(BaseModel):
    """Configuration describing retry behaviour for trigger-driven runs."""

    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(
        default=3,
        ge=1,
        description="Total attempts including the initial execution.",
    )
    initial_delay_seconds: float = Field(
        default=30.0,
        ge=0.0,
        description="Delay applied before the first retry attempt.",
    )
    backoff_factor: float = Field(
        default=2.0,
        ge=1.0,
        description="Multiplier applied to the delay after each failed attempt.",
    )
    max_delay_seconds: float | None = Field(
        default=300.0,
        ge=0.0,
        description="Optional ceiling for computed retry delays.",
    )
    jitter_factor: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description=(
            "Percentage of jitter applied to each delay. Values are expressed "
            "as a fraction of the computed delay."
        ),
    )

    def compute_delay_seconds(
        self,
        *,
        attempt_index: int,
        random_state: Random | None = None,
    ) -> float:
        """Return the delay in seconds before the provided retry attempt."""
        if attempt_index < 0:
            raise RetryPolicyValidationError("attempt_index must be non-negative")

        delay = self.initial_delay_seconds * (self.backoff_factor**attempt_index)
        if self.max_delay_seconds is not None:
            delay = min(delay, self.max_delay_seconds)

        jitter_factor = self.jitter_factor
        if jitter_factor and delay:
            rng = random_state or Random()
            jitter_window = delay * jitter_factor
            jitter = rng.uniform(-jitter_window, jitter_window)
            delay = max(0.0, delay + jitter)

        return delay


@dataclass(slots=True)
class RetryDecision:
    """Represents a single retry attempt scheduling decision."""

    retry_number: int
    scheduled_for: datetime
    delay_seconds: float


class RetryPolicyState:
    """Track retry attempts and compute scheduling decisions."""

    def __init__(
        self,
        config: RetryPolicyConfig | None = None,
        *,
        random_state: Random | None = None,
    ) -> None:
        """Initialize the retry policy state with optional overrides."""
        self._config = (config or RetryPolicyConfig()).model_copy(deep=True)
        self._random = random_state or Random()
        self._scheduled_retries = 0

    @property
    def config(self) -> RetryPolicyConfig:
        """Return a deep copy of the retry configuration."""
        return self._config.model_copy(deep=True)

    @property
    def remaining_attempts(self) -> int:
        """Return the remaining retry attempts available."""
        max_retries = max(self._config.max_attempts - 1, 0)
        return max(0, max_retries - self._scheduled_retries)

    def reset(self) -> None:
        """Reset the retry tracker so a new run can start fresh."""
        self._scheduled_retries = 0

    def next_retry(
        self,
        *,
        failed_at: datetime | None = None,
    ) -> RetryDecision | None:
        """Return the next retry decision or ``None`` when exhausted."""
        if self.remaining_attempts <= 0:
            return None

        attempt_index = self._scheduled_retries
        delay_seconds = self._config.compute_delay_seconds(
            attempt_index=attempt_index,
            random_state=self._random,
        )

        base_time = failed_at or datetime.now(tz=UTC)
        scheduled_for = base_time + timedelta(seconds=delay_seconds)

        self._scheduled_retries += 1
        return RetryDecision(
            retry_number=attempt_index + 1,
            scheduled_for=scheduled_for,
            delay_seconds=delay_seconds,
        )


__all__ = [
    "RetryPolicyConfig",
    "RetryPolicyState",
    "RetryPolicyValidationError",
    "RetryDecision",
]
