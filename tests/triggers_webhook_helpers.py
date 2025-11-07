from __future__ import annotations
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any
from pydantic import ValidationError
from orcheo.triggers.webhook import WebhookRequest, WebhookValidationError


def make_request(**overrides: object) -> WebhookRequest:
    """Construct webhook requests with sensible defaults for tests."""

    params: dict[str, object] = {
        "method": "POST",
        "headers": {},
        "query_params": {},
        "payload": None,
    }
    params.update(overrides)
    return WebhookRequest(**params)  # type: ignore[arg-type]


def extract_inner_error(exc: ValidationError) -> WebhookValidationError:
    """Retrieve the underlying webhook validation error from a Pydantic error."""

    inner = exc.errors()[0]["ctx"]["error"]
    assert isinstance(inner, WebhookValidationError)
    return inner


def sign_payload(
    payload: Any,
    *,
    secret: str,
    algorithm: str = "sha256",
    timestamp: datetime | None = None,
) -> tuple[str, str | None]:
    """Return a signature matching the webhook validation logic."""

    if timestamp is None:
        timestamp = datetime.now(tz=UTC)
    if isinstance(payload, bytes):
        payload_bytes = payload
    elif isinstance(payload, str):
        payload_bytes = payload.encode("utf-8")
    else:
        canonical_payload = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        payload_bytes = canonical_payload.encode("utf-8")
    parts: list[bytes] = []
    if timestamp:
        parts.append(str(int(timestamp.timestamp())).encode("utf-8"))
    parts.append(payload_bytes)
    message = b".".join(parts)
    digest = hmac.new(secret.encode("utf-8"), message, getattr(hashlib, algorithm))
    return digest.hexdigest(), str(int(timestamp.timestamp()))


__all__ = [
    "extract_inner_error",
    "make_request",
    "sign_payload",
]
