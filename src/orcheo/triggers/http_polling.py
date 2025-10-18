"""HTTP polling trigger configuration and execution helpers."""

from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any
import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class HttpPollingError(RuntimeError):
    """Raised when polling encounters unrecoverable errors."""


class HttpPollingConfig(BaseModel):
    """Configuration describing the polling cadence and request metadata."""

    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    interval_seconds: int = Field(default=300, ge=30, description="Polling cadence")
    method: str = Field(default="GET")
    headers: dict[str, str] = Field(default_factory=dict)
    query: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=10.0, gt=0)

    @field_validator("method")
    @classmethod
    def _normalize_method(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"GET", "POST", "PUT", "PATCH"}:
            msg = f"Unsupported HTTP method for polling: {value}"
            raise ValueError(msg)
        return normalized


@dataclass
class HttpPollingState:
    """Track polling state for change detection and scheduling."""

    config: HttpPollingConfig
    last_polled_at: datetime | None = None
    last_signature: str | None = None

    def due(self, *, now: datetime) -> bool:
        """Return True when the polling interval has elapsed."""
        if self.last_polled_at is None:
            return True
        interval = timedelta(seconds=self.config.interval_seconds)
        return now >= self.last_polled_at + interval

    def mark_polled(self, *, polled_at: datetime, signature: str | None) -> None:
        """Persist the polling timestamp and response signature."""
        self.last_polled_at = polled_at
        if signature is not None:
            self.last_signature = signature

    def request_kwargs(self) -> dict[str, Any]:
        """Return keyword arguments for httpx.Client.request."""
        return {
            "method": self.config.method,
            "url": str(self.config.url),
            "headers": self.config.headers,
            "params": self.config.query,
            "timeout": self.config.timeout_seconds,
        }

    def compute_signature(self, *, body: bytes, headers: Mapping[str, str]) -> str:
        """Compute a stable signature for deduplicating responses."""
        etag = headers.get("etag") or headers.get("ETag")
        if etag:
            return etag
        digest = sha256()
        digest.update(body)
        return digest.hexdigest()

    def should_emit(self, signature: str) -> bool:
        """Return whether the response represents a new change."""
        return signature != self.last_signature

    def poll(self) -> tuple[dict[str, Any], str | None]:
        """Perform the HTTP request and return serialized payload and signature."""
        kwargs = self.request_kwargs()
        try:
            with httpx.Client() as client:
                response = client.request(**kwargs)
        except Exception as exc:  # pragma: no cover - httpx handles networking
            raise HttpPollingError(str(exc)) from exc
        signature = self.compute_signature(
            body=response.content,
            headers=response.headers,
        )
        payload: dict[str, Any] = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": _safe_json(response),
            "raw": response.text,
        }
        return payload, signature


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return None


__all__ = [
    "HttpPollingConfig",
    "HttpPollingError",
    "HttpPollingState",
]
