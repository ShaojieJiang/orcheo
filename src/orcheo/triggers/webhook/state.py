"""Webhook trigger state management and validation logic."""

from __future__ import annotations
import hashlib
import hmac
import json
from collections import deque
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from orcheo.triggers.webhook.config import WebhookTriggerConfig
from orcheo.triggers.webhook.errors import (
    MethodNotAllowedError,
    RateLimitExceededError,
    WebhookAuthenticationError,
    WebhookValidationError,
)
from orcheo.triggers.webhook.request import WebhookRequest


class WebhookTriggerState:
    """Maintain webhook configuration and request validation state."""

    def __init__(self, config: WebhookTriggerConfig | None = None) -> None:
        """Initialize state with an optional configuration instance."""
        self._config = (config or WebhookTriggerConfig()).model_copy(deep=True)
        self._recent_invocations: deque[datetime] = deque()
        self._recent_signatures: deque[tuple[str, datetime]] = deque()
        self._signature_cache: set[str] = set()

    @property
    def config(self) -> WebhookTriggerConfig:
        """Return a deep copy of the stored webhook configuration."""
        return self._config.model_copy(deep=True)

    def update_config(self, config: WebhookTriggerConfig) -> None:
        """Replace the configuration and reset rate limiting state."""
        self._config = config.model_copy(deep=True)
        self._recent_invocations.clear()
        self._recent_signatures.clear()
        self._signature_cache.clear()

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

    def scrub_headers_for_storage(self, headers: Mapping[str, str]) -> dict[str, str]:
        """Redact sensitive headers such as shared secrets before storage."""
        sanitized = {key: value for key, value in headers.items()}
        secret_header = self._config.shared_secret_header
        if secret_header:
            sanitized.pop(secret_header, None)
        signature_header = self._config.hmac_header
        if signature_header:
            sanitized.pop(signature_header, None)
        return sanitized

    # Internal helpers -------------------------------------------------

    def _validate_method(self, request: WebhookRequest) -> None:
        allowed = set(self._config.allowed_methods)
        method = request.normalized_method()
        if method not in allowed:
            raise MethodNotAllowedError(method, allowed)

    def _validate_authentication(self, request: WebhookRequest) -> None:
        if self._config.hmac_secret:
            self._validate_hmac_signature(request)
        if self._config.shared_secret:
            self._validate_shared_secret(request)

    def _validate_shared_secret(self, request: WebhookRequest) -> None:
        header_name = self._config.shared_secret_header
        if header_name is None:
            return  # pragma: no cover - defensive

        expected = self._config.shared_secret
        provided = request.normalized_headers().get(header_name)
        if expected is None or provided is None:
            raise WebhookAuthenticationError()
        if not hmac.compare_digest(provided, expected):
            raise WebhookAuthenticationError()

    def _validate_hmac_signature(self, request: WebhookRequest) -> None:
        header_name = self._config.hmac_header
        secret = self._config.hmac_secret
        if header_name is None or not secret:
            return

        headers = request.normalized_headers()
        provided_raw = headers.get(header_name)
        if not provided_raw:
            raise WebhookAuthenticationError()
        signature = self._extract_hmac_signature(provided_raw)

        timestamp_header = self._config.hmac_timestamp_header
        if timestamp_header:
            timestamp_value = headers.get(timestamp_header)
            if not timestamp_value:
                raise WebhookAuthenticationError()
            timestamp = self._parse_signature_timestamp(timestamp_value)
        else:
            timestamp = None

        payload_bytes = self._canonical_payload_bytes(request.payload)
        components: list[bytes] = []
        if timestamp is not None:
            components.append(str(int(timestamp.timestamp())).encode("utf-8"))
        components.append(payload_bytes)
        message = b".".join(components)

        hasher = getattr(hashlib, self._config.hmac_algorithm)
        expected = hmac.new(secret.encode("utf-8"), message, hasher).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise WebhookAuthenticationError()

        self._enforce_signature_replay(signature, timestamp)

    def _canonical_payload_bytes(self, payload: Any) -> bytes:
        if payload is None:
            return b""
        if isinstance(payload, bytes):
            return payload
        if isinstance(payload, str):
            return payload.encode("utf-8")
        try:
            serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):  # pragma: no cover - defensive
            serialized = str(payload)
        return serialized.encode("utf-8")

    def _extract_hmac_signature(self, raw: str) -> str:
        candidate = raw.strip()
        if not candidate:
            raise WebhookAuthenticationError()
        for segment in candidate.split(","):
            part = segment.strip()
            if "=" in part:
                key, value = part.split("=", 1)
                if key.lower() in {"sha256", "sha512", "v1", "signature"}:
                    candidate = value.strip()
        if not candidate:
            raise WebhookAuthenticationError()
        return candidate

    def _parse_signature_timestamp(self, value: str) -> datetime:
        stripped = value.strip()
        if not stripped:
            raise WebhookAuthenticationError()
        if stripped.isdigit():
            timestamp = datetime.fromtimestamp(int(stripped), tz=UTC)
        else:
            try:
                timestamp = datetime.fromisoformat(stripped.replace("Z", "+00:00"))
            except ValueError as exc:  # pragma: no cover - defensive
                raise WebhookAuthenticationError() from exc

        tolerance = self._config.hmac_tolerance_seconds
        if tolerance:
            now = datetime.now(tz=UTC)
            if abs((now - timestamp).total_seconds()) > tolerance:
                raise WebhookAuthenticationError()
        return timestamp

    def _enforce_signature_replay(
        self, signature: str, timestamp: datetime | None
    ) -> None:
        tolerance = max(self._config.hmac_tolerance_seconds, 1)
        now = datetime.now(tz=UTC)
        cutoff = now - timedelta(seconds=tolerance)
        while self._recent_signatures and self._recent_signatures[0][1] < cutoff:
            old_signature, _ = self._recent_signatures.popleft()
            self._signature_cache.discard(old_signature)
        if signature in self._signature_cache:
            raise WebhookAuthenticationError()
        self._signature_cache.add(signature)
        self._recent_signatures.append((signature, timestamp or now))

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


__all__ = ["WebhookTriggerState"]
