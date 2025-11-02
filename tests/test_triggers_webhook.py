from __future__ import annotations
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any
import pytest
from pydantic import ValidationError
from orcheo.triggers.webhook import (
    RateLimitConfig,
    RateLimitExceededError,
    WebhookAuthenticationError,
    WebhookRequest,
    WebhookTriggerConfig,
    WebhookTriggerState,
    WebhookValidationError,
)


def make_request(**overrides: object) -> WebhookRequest:
    """Helper to construct webhook requests with sensible defaults."""

    params: dict[str, object] = {
        "method": "POST",
        "headers": {},
        "query_params": {},
        "payload": None,
    }
    params.update(overrides)
    return WebhookRequest(**params)  # type: ignore[arg-type]


def _extract_inner_error(exc: ValidationError) -> WebhookValidationError:
    """Retrieve the underlying webhook error from a validation error."""

    inner = exc.errors()[0]["ctx"]["error"]
    assert isinstance(inner, WebhookValidationError)
    return inner


def _sign_payload(
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


def test_webhook_config_rejects_empty_methods() -> None:
    """Webhook configuration must allow at least one HTTP method."""

    with pytest.raises(ValidationError) as exc:
        WebhookTriggerConfig(allowed_methods=[])

    inner = _extract_inner_error(exc.value)
    assert inner.status_code == 400
    assert "At least one HTTP method" in str(inner)


@pytest.mark.parametrize(
    "config_kwargs",
    [
        {"shared_secret_header": "x-hook-secret"},
        {"shared_secret": "secret-value"},
    ],
)
def test_webhook_config_requires_secret_pairs(config_kwargs: dict[str, str]) -> None:
    """Secret header and value must be provided together."""

    with pytest.raises(ValidationError) as exc:
        WebhookTriggerConfig(**config_kwargs)

    inner = _extract_inner_error(exc.value)
    assert inner.status_code == 400


def test_webhook_authentication_error_includes_status_code() -> None:
    """Invalid authentication should raise the dedicated error."""

    config = WebhookTriggerConfig(
        shared_secret_header="x-secret",
        shared_secret="expected",
    )
    state = WebhookTriggerState(config)

    request = make_request(headers={"x-secret": "invalid"})

    with pytest.raises(WebhookAuthenticationError) as exc:
        state.validate(request)

    assert exc.value.status_code == 401


def test_webhook_missing_secret_header_is_rejected() -> None:
    """Requests omitting the shared secret header should be denied."""

    config = WebhookTriggerConfig(
        shared_secret_header="x-secret",
        shared_secret="expected",
    )
    state = WebhookTriggerState(config)

    with pytest.raises(WebhookAuthenticationError):
        state.validate(make_request(headers={}))


def test_webhook_state_scrubs_shared_secret_header() -> None:
    """Shared secret headers should be removed before persisting metadata."""

    config = WebhookTriggerConfig(
        shared_secret_header="x-secret",
        shared_secret="expected",
    )
    state = WebhookTriggerState(config)
    sanitized = state.scrub_headers_for_storage(
        {"x-secret": "expected", "content-type": "application/json"}
    )

    assert "x-secret" not in sanitized
    assert sanitized["content-type"] == "application/json"


def test_webhook_required_headers_validation() -> None:
    """Missing required headers should fail validation with status 400."""

    config = WebhookTriggerConfig(required_headers={"X-Custom": "expected"})
    state = WebhookTriggerState(config)

    request = make_request(headers={})

    with pytest.raises(WebhookValidationError) as exc:
        state.validate(request)

    assert exc.value.status_code == 400
    assert "header" in str(exc.value)


def test_webhook_required_headers_success() -> None:
    """Requests with all required headers should succeed."""

    config = WebhookTriggerConfig(required_headers={"X-Custom": "expected"})
    state = WebhookTriggerState(config)

    state.validate(make_request(headers={"X-Custom": "expected"}))


def test_webhook_required_query_validation() -> None:
    """Missing required query parameters should fail validation."""

    config = WebhookTriggerConfig(required_query_params={"token": "abc"})
    state = WebhookTriggerState(config)

    request = make_request(query_params={})

    with pytest.raises(WebhookValidationError) as exc:
        state.validate(request)

    assert exc.value.status_code == 400
    assert "query" in str(exc.value)


def test_webhook_required_query_success() -> None:
    """Requests containing required query parameters should validate."""

    config = WebhookTriggerConfig(required_query_params={"token": "abc"})
    state = WebhookTriggerState(config)

    state.validate(make_request(query_params={"token": "abc"}))


def test_webhook_rate_limit_purges_outdated_entries() -> None:
    """Rate limit enforcement should drop invocations outside the window."""

    config = WebhookTriggerConfig(
        rate_limit=RateLimitConfig(limit=2, interval_seconds=1)
    )
    state = WebhookTriggerState(config)

    stale_time = datetime.now(tz=UTC) - timedelta(seconds=5)
    state._recent_invocations.append(stale_time)

    state.validate(make_request())

    assert len(state._recent_invocations) == 1
    assert state._recent_invocations[0] >= stale_time


def test_webhook_rate_limit_exceeded() -> None:
    """Exceeding the configured rate limit should raise an error."""

    config = WebhookTriggerConfig(
        rate_limit=RateLimitConfig(limit=1, interval_seconds=60)
    )
    state = WebhookTriggerState(config)

    state.validate(make_request())

    with pytest.raises(RateLimitExceededError):
        state.validate(make_request())


def test_webhook_validates_hmac_signature() -> None:
    """Valid HMAC signatures should be accepted."""

    secret = "super-secret"
    algorithm = "sha256"
    payload = {"foo": "bar", "count": 3}
    timestamp = datetime.now(tz=UTC)
    signature, ts_value = _sign_payload(
        payload,
        secret=secret,
        algorithm=algorithm,
        timestamp=timestamp,
    )

    config = WebhookTriggerConfig(
        hmac_header="x-signature",
        hmac_secret=secret,
        hmac_algorithm=algorithm,
        hmac_timestamp_header="x-signature-ts",
        hmac_tolerance_seconds=600,
    )
    state = WebhookTriggerState(config)

    state.validate(
        make_request(
            payload=payload,
            headers={
                "x-signature": signature,
                "x-signature-ts": ts_value,
            },
        )
    )


def test_webhook_rejects_invalid_hmac_signature() -> None:
    """Invalid HMAC signatures should be rejected with 401."""

    secret = "super-secret"
    payload = {"foo": "bar"}
    timestamp = datetime.now(tz=UTC)
    signature, ts_value = _sign_payload(
        payload,
        secret=secret,
        timestamp=timestamp,
    )

    config = WebhookTriggerConfig(
        hmac_header="x-signature",
        hmac_secret=secret,
        hmac_timestamp_header="x-signature-ts",
        hmac_tolerance_seconds=600,
    )
    state = WebhookTriggerState(config)

    with pytest.raises(WebhookAuthenticationError):
        state.validate(
            make_request(
                payload=payload,
                headers={
                    "x-signature": signature[:-1] + "0",
                    "x-signature-ts": ts_value,
                },
            )
        )


def test_webhook_hmac_requires_timestamp_when_configured() -> None:
    """Timestamp header must be present when configured for HMAC verification."""

    secret = "super-secret"
    payload = {"foo": "bar"}
    signature, _ = _sign_payload(payload, secret=secret)

    config = WebhookTriggerConfig(
        hmac_header="x-signature",
        hmac_secret=secret,
        hmac_timestamp_header="x-signature-ts",
    )
    state = WebhookTriggerState(config)

    with pytest.raises(WebhookAuthenticationError):
        state.validate(
            make_request(payload=payload, headers={"x-signature": signature})
        )


def test_webhook_hmac_replay_protection() -> None:
    """Replaying the same signature should trigger authentication failure."""

    secret = "super-secret"
    payload = {"foo": "bar"}
    timestamp = datetime.now(tz=UTC)
    signature, ts_value = _sign_payload(
        payload,
        secret=secret,
        timestamp=timestamp,
    )

    config = WebhookTriggerConfig(
        hmac_header="x-signature",
        hmac_secret=secret,
        hmac_timestamp_header="x-signature-ts",
        hmac_tolerance_seconds=600,
    )
    state = WebhookTriggerState(config)

    request = make_request(
        payload=payload,
        headers={
            "x-signature": signature,
            "x-signature-ts": ts_value,
        },
    )

    state.validate(request)

    with pytest.raises(WebhookAuthenticationError):
        state.validate(request)


def test_webhook_hmac_timestamp_tolerance() -> None:
    """Signatures outside the tolerance window should be rejected."""

    secret = "super-secret"
    payload = {"foo": "bar"}
    old_timestamp = datetime.now(tz=UTC) - timedelta(seconds=1000)
    signature, ts_value = _sign_payload(
        payload,
        secret=secret,
        timestamp=old_timestamp,
    )

    config = WebhookTriggerConfig(
        hmac_header="x-signature",
        hmac_secret=secret,
        hmac_timestamp_header="x-signature-ts",
        hmac_tolerance_seconds=300,
    )
    state = WebhookTriggerState(config)

    with pytest.raises(WebhookAuthenticationError):
        state.validate(
            make_request(
                payload=payload,
                headers={
                    "x-signature": signature,
                    "x-signature-ts": ts_value,
                },
            )
        )
