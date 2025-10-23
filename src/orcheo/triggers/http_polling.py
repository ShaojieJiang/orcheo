"""HTTP polling trigger configuration and scheduling helpers."""

from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class HttpPollingValidationError(ValueError):
    """Raised when HTTP polling trigger configuration fails validation."""


class HttpPollingTriggerConfig(BaseModel):
    """Configuration describing how HTTP polling should execute."""

    model_config = ConfigDict(extra="forbid")

    url: AnyHttpUrl = Field(
        description="HTTP endpoint that will be polled for changes.",
    )
    method: str = Field(
        default="GET",
        description="HTTP method used when performing polling requests.",
    )
    headers: Mapping[str, str] = Field(
        default_factory=dict,
        description="Additional headers applied to polling requests.",
    )
    query_params: Mapping[str, str] = Field(
        default_factory=dict,
        description="Query parameters appended to the polling request.",
    )
    body: dict[str, Any] | None = Field(
        default=None,
        description="Optional JSON payload submitted with the request.",
    )
    interval_seconds: int = Field(
        default=300,
        ge=10,
        le=86400,
        description="Number of seconds between polling attempts.",
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Timeout in seconds applied to polling requests.",
    )
    verify_tls: bool = Field(
        default=True,
        description="Whether TLS certificates should be validated.",
    )
    follow_redirects: bool = Field(
        default=False,
        description="Whether HTTP redirects should be followed.",
    )
    deduplicate_on: str | None = Field(
        default=None,
        description=(
            "Optional JSON pointer describing which response attribute is used to"
            " deduplicate polling results."
        ),
    )

    @field_validator("method")
    @classmethod
    def _normalize_method(cls, value: str) -> str:
        normalized = value.strip().upper()
        allowed = {"GET", "POST", "PUT", "PATCH", "DELETE"}
        if normalized not in allowed:
            msg = "HTTP polling method must be one of " + ", ".join(sorted(allowed))
            raise HttpPollingValidationError(msg)
        return normalized

    @field_validator("headers", "query_params", mode="after")
    @classmethod
    def _normalize_mapping(cls, value: Mapping[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, val in value.items():
            normalized[str(key).strip()] = str(val)
        return normalized

    @field_validator("deduplicate_on")
    @classmethod
    def _validate_deduplicate(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized.startswith("/"):
            msg = "deduplicate_on must be a JSON pointer starting with '/'"
            raise HttpPollingValidationError(msg)
        return normalized


@dataclass(slots=True)
class HttpPollingDispatchPlan:
    """Dispatch plan generated when an HTTP polling run should execute."""

    scheduled_for: datetime
    request_url: str
    method: str


class HttpPollingTriggerState:
    """State container tracking HTTP polling schedule progression."""

    def __init__(
        self,
        config: HttpPollingTriggerConfig | None = None,
    ) -> None:
        """Initialize the polling state container."""
        default_url = cast(AnyHttpUrl, "http://localhost")
        self._config = (config or HttpPollingTriggerConfig(url=default_url)).model_copy(
            deep=True
        )
        self._next_poll_at: datetime | None = None

    @property
    def config(self) -> HttpPollingTriggerConfig:
        """Return a deep copy of the stored configuration."""
        return self._config.model_copy(deep=True)

    def update_config(self, config: HttpPollingTriggerConfig) -> None:
        """Replace the stored configuration and reset scheduling cursor."""
        self._config = config.model_copy(deep=True)
        self._next_poll_at = None

    def ensure_next_poll(self, *, now: datetime | None = None) -> datetime:
        """Ensure the next poll timestamp is calculated and return it."""
        reference = now or datetime.now(UTC)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        if self._next_poll_at is None or self._next_poll_at <= reference:
            interval = timedelta(seconds=self._config.interval_seconds)
            self._next_poll_at = reference + interval
        return self._next_poll_at

    def consume_poll(self, *, now: datetime | None = None) -> HttpPollingDispatchPlan:
        """Consume the scheduled poll and advance to the next interval."""
        scheduled_for = self.ensure_next_poll(now=now)
        plan = HttpPollingDispatchPlan(
            scheduled_for=scheduled_for,
            request_url=str(self._config.url),
            method=self._config.method,
        )
        interval = timedelta(seconds=self._config.interval_seconds)
        self._next_poll_at = scheduled_for + interval
        return plan


__all__ = [
    "HttpPollingTriggerConfig",
    "HttpPollingTriggerState",
    "HttpPollingDispatchPlan",
    "HttpPollingValidationError",
]
