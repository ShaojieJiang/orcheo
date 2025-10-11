"""Webhook trigger configuration and validation helpers."""

from __future__ import annotations
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WebhookValidationError(ValueError):
    """Base error raised when webhook requests fail validation."""

    def __init__(self, message: str, *, status_code: int) -> None:
        """Store the error message alongside the HTTP status code."""
        super().__init__(message)
        self.status_code = status_code


class MethodNotAllowedError(WebhookValidationError):
    """Raised when the inbound request method is not permitted."""

    def __init__(self, method: str, allowed: set[str]) -> None:
        """Initialize the error with the offending method and allowed set."""
        allowed_methods = ", ".join(sorted(allowed)) or "none"
        message = f"Method {method} not allowed. Allowed methods: {allowed_methods}"
        super().__init__(message, status_code=405)


class WebhookAuthenticationError(WebhookValidationError):
    """Raised when the request fails shared secret validation."""

    def __init__(self) -> None:
        """Construct the error using a fixed authentication failure message."""
        super().__init__("Invalid webhook authentication credentials", status_code=401)


class RateLimitExceededError(WebhookValidationError):
    """Raised when requests exceed the configured rate limit."""

    def __init__(self, limit: int, interval_seconds: int) -> None:
        """Include the configured limit and interval in the error message."""
        message = (
            "Webhook rate limit exceeded. "
            f"Limit: {limit} requests per {interval_seconds} seconds"
        )
        super().__init__(message, status_code=429)


class RateLimitConfig(BaseModel):
    """Configuration describing webhook rate limiting behaviour."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(
        default=60,
        ge=1,
        description="Maximum number of requests allowed in the configured interval.",
    )
    interval_seconds: int = Field(
        default=60,
        ge=1,
        description="Time window in seconds over which the limit is applied.",
    )


class WebhookTriggerConfig(BaseModel):
    """Configuration defining webhook trigger validation rules."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    allowed_methods: list[str] = Field(
        default_factory=lambda: ["POST"],
        description="Set of HTTP methods that are permitted for the webhook.",
    )
    required_headers: dict[str, str] = Field(
        default_factory=dict,
        description="Headers that must be present with specific values.",
    )
    required_query_params: dict[str, str] = Field(
        default_factory=dict,
        description="Query parameters that must match expected values.",
    )
    shared_secret_header: str | None = Field(
        default=None,
        alias="secret_header",
        serialization_alias="secret_header",
        description="Optional HTTP header used to supply a shared secret.",
    )
    shared_secret: str | None = Field(
        default=None,
        description="Optional shared secret value used to authenticate requests.",
    )
    rate_limit: RateLimitConfig | None = Field(
        default=None,
        description="Optional rate limit configuration for inbound requests.",
    )

    @field_validator("allowed_methods", mode="after")
    @classmethod
    def _normalize_methods(cls, value: list[str]) -> list[str]:
        methods = sorted({method.upper() for method in value})
        if not methods:
            raise WebhookValidationError(
                "At least one HTTP method must be allowed", status_code=400
            )
        return methods

    @field_validator("required_headers", mode="after")
    @classmethod
    def _normalize_required_headers(cls, value: dict[str, str]) -> dict[str, str]:
        return {key.lower(): str(val) for key, val in value.items()}

    @field_validator("required_query_params", mode="after")
    @classmethod
    def _normalize_required_query(cls, value: dict[str, str]) -> dict[str, str]:
        return {str(key): str(val) for key, val in value.items()}

    @field_validator("shared_secret_header")
    @classmethod
    def _normalize_secret_header(cls, value: str | None) -> str | None:
        return value if value is None else value.lower()

    @model_validator(mode="after")
    def _validate_secret_configuration(self) -> WebhookTriggerConfig:
        if self.shared_secret_header and not self.shared_secret:
            raise WebhookValidationError(
                "shared_secret must be provided when shared_secret_header is set",
                status_code=400,
            )
        if self.shared_secret and not self.shared_secret_header:
            raise WebhookValidationError(
                "shared_secret_header is required when shared_secret is provided",
                status_code=400,
            )
        return self


@dataclass(slots=True)
class WebhookRequest:
    """Normalized representation of an inbound webhook request."""

    method: str
    headers: Mapping[str, str]
    query_params: Mapping[str, str]
    payload: Any
    source_ip: str | None = None

    def normalized_method(self) -> str:
        """Return the uppercase HTTP method."""
        return self.method.upper()

    def normalized_headers(self) -> dict[str, str]:
        """Return headers normalized to lowercase keys."""
        return {key.lower(): value for key, value in self.headers.items()}

    def normalized_query(self) -> dict[str, str]:
        """Return a shallow copy of the query parameters."""
        return dict(self.query_params)


class WebhookTriggerState:
    """Maintain webhook configuration and request validation state."""

    def __init__(self, config: WebhookTriggerConfig | None = None) -> None:
        """Initialize state with an optional configuration instance."""
        self._config = (config or WebhookTriggerConfig()).model_copy(deep=True)
        self._recent_invocations: deque[datetime] = deque()

    @property
    def config(self) -> WebhookTriggerConfig:
        """Return a deep copy of the stored webhook configuration."""
        return self._config.model_copy(deep=True)

    def update_config(self, config: WebhookTriggerConfig) -> None:
        """Replace the configuration and reset rate limiting state."""
        self._config = config.model_copy(deep=True)
        self._recent_invocations.clear()

    def validate(self, request: WebhookRequest) -> None:
        """Validate the inbound request against the configured rules."""
        self._validate_method(request)
        self._validate_required_headers(request)
        self._validate_required_query_params(request)
        self._validate_authentication(request)
        self._enforce_rate_limit()

    def serialize_payload(self, payload: Any) -> Any:
        """Normalize payloads for storage on workflow runs."""
        if isinstance(payload, bytes):
            decoded = payload.decode("utf-8", errors="replace")
            return {"raw": decoded}
        return payload

    # Internal helpers -------------------------------------------------

    def _validate_method(self, request: WebhookRequest) -> None:
        allowed = set(self._config.allowed_methods)
        method = request.normalized_method()
        if method not in allowed:
            raise MethodNotAllowedError(method, allowed)

    def _validate_authentication(self, request: WebhookRequest) -> None:
        header_name = self._config.shared_secret_header
        if header_name is None:
            return

        expected = self._config.shared_secret
        provided = request.normalized_headers().get(header_name)
        if expected is None or provided != expected:
            raise WebhookAuthenticationError()

    def _validate_required_headers(self, request: WebhookRequest) -> None:
        expected = self._config.required_headers
        if not expected:
            return

        headers = request.normalized_headers()
        for key, value in expected.items():
            if headers.get(key) != value:
                message = f"Missing or invalid required header: {key}"
                raise WebhookValidationError(message, status_code=400)

    def _validate_required_query_params(self, request: WebhookRequest) -> None:
        expected = self._config.required_query_params
        if not expected:
            return

        params = request.normalized_query()
        for key, value in expected.items():
            if params.get(key) != value:
                message = f"Missing or invalid required query parameter: {key}"
                raise WebhookValidationError(message, status_code=400)

    def _enforce_rate_limit(self) -> None:
        config = self._config.rate_limit
        if config is None:
            return

        now = datetime.now(tz=UTC)
        window_start = now - timedelta(seconds=config.interval_seconds)

        while self._recent_invocations and self._recent_invocations[0] < window_start:
            self._recent_invocations.popleft()

        if len(self._recent_invocations) >= config.limit:
            raise RateLimitExceededError(config.limit, config.interval_seconds)

        self._recent_invocations.append(now)
