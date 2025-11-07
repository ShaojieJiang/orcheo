"""Pydantic models that describe webhook trigger configuration."""

from __future__ import annotations
import hashlib
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from orcheo.triggers.webhook.errors import WebhookValidationError


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
    hmac_header: str | None = Field(
        default=None,
        description="Header containing the HMAC signature for the payload.",
    )
    hmac_secret: str | None = Field(
        default=None,
        description="Secret used to compute the HMAC signature.",
    )
    hmac_algorithm: str = Field(
        default="sha256",
        description="Hash algorithm used when computing the HMAC signature.",
    )
    hmac_timestamp_header: str | None = Field(
        default=None,
        description="Optional header containing the signature timestamp.",
    )
    hmac_tolerance_seconds: int = Field(
        default=300,
        ge=0,
        description="Maximum age for HMAC signatures in seconds.",
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

    @field_validator("hmac_header")
    @classmethod
    def _normalize_hmac_header(cls, value: str | None) -> str | None:
        return value if value is None else value.lower()

    @field_validator("hmac_timestamp_header")
    @classmethod
    def _normalize_timestamp_header(cls, value: str | None) -> str | None:
        return value if value is None else value.lower()

    @field_validator("hmac_algorithm")
    @classmethod
    def _validate_algorithm(cls, value: str) -> str:
        candidate = value.strip().lower()
        if candidate not in hashlib.algorithms_available:
            raise WebhookValidationError(
                f"Unsupported HMAC algorithm: {value}", status_code=400
            )
        return candidate

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
        if (self.hmac_header and not self.hmac_secret) or (
            self.hmac_secret and not self.hmac_header
        ):
            raise WebhookValidationError(
                "hmac_header and hmac_secret must be configured together",
                status_code=400,
            )
        return self


__all__ = ["RateLimitConfig", "WebhookTriggerConfig"]
