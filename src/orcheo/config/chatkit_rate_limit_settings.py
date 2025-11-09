"""Configuration model for ChatKit rate limiting."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any, ClassVar, cast
from pydantic import BaseModel, Field
from orcheo.config.defaults import _DEFAULTS


class ChatKitRateLimitSettings(BaseModel):
    """Validated rate limit configuration for ChatKit endpoints."""

    ip_limit: int = Field(
        default=cast(int, _DEFAULTS["CHATKIT_RATE_LIMIT_IP_LIMIT"]), ge=0
    )
    ip_interval_seconds: int = Field(
        default=cast(int, _DEFAULTS["CHATKIT_RATE_LIMIT_IP_INTERVAL"]), gt=0
    )
    jwt_limit: int = Field(
        default=cast(int, _DEFAULTS["CHATKIT_RATE_LIMIT_JWT_LIMIT"]), ge=0
    )
    jwt_interval_seconds: int = Field(
        default=cast(int, _DEFAULTS["CHATKIT_RATE_LIMIT_JWT_INTERVAL"]), gt=0
    )
    publish_limit: int = Field(
        default=cast(int, _DEFAULTS["CHATKIT_RATE_LIMIT_PUBLISH_LIMIT"]), ge=0
    )
    publish_interval_seconds: int = Field(
        default=cast(int, _DEFAULTS["CHATKIT_RATE_LIMIT_PUBLISH_INTERVAL"]), gt=0
    )
    session_limit: int = Field(
        default=cast(int, _DEFAULTS["CHATKIT_RATE_LIMIT_SESSION_LIMIT"]), ge=0
    )
    session_interval_seconds: int = Field(
        default=cast(int, _DEFAULTS["CHATKIT_RATE_LIMIT_SESSION_INTERVAL"]), gt=0
    )

    _FIELD_TO_ENV: ClassVar[dict[str, str]] = {
        "ip_limit": "CHATKIT_RATE_LIMIT_IP_LIMIT",
        "ip_interval_seconds": "CHATKIT_RATE_LIMIT_IP_INTERVAL",
        "jwt_limit": "CHATKIT_RATE_LIMIT_JWT_LIMIT",
        "jwt_interval_seconds": "CHATKIT_RATE_LIMIT_JWT_INTERVAL",
        "publish_limit": "CHATKIT_RATE_LIMIT_PUBLISH_LIMIT",
        "publish_interval_seconds": "CHATKIT_RATE_LIMIT_PUBLISH_INTERVAL",
        "session_limit": "CHATKIT_RATE_LIMIT_SESSION_LIMIT",
        "session_interval_seconds": "CHATKIT_RATE_LIMIT_SESSION_INTERVAL",
    }

    @classmethod
    def from_mapping(cls, source: Mapping[str, Any]) -> ChatKitRateLimitSettings:
        """Create settings from a Dynaconf-like mapping."""
        kwargs: dict[str, Any] = {}
        for field_name, env_key in cls._FIELD_TO_ENV.items():
            value = source.get(env_key)
            if value is not None:
                kwargs[field_name] = value
        return cls(**kwargs)


__all__ = ["ChatKitRateLimitSettings"]
