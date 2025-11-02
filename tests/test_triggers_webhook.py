from __future__ import annotations
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any
import pytest
from pydantic import ValidationError
from orcheo.triggers.webhook import (
    MethodNotAllowedError,
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
        {"secret_header": "x-hook-secret"},
        {"shared_secret": "secret-value"},
    ],
)
def test_webhook_config_requires_secret_pairs(config_kwargs: dict[str, str]) -> None:
    """Secret header and value must be provided together."""

    with pytest.raises(ValidationError) as exc:
        WebhookTriggerConfig(**config_kwargs)  # type: ignore[arg-type]

    inner = _extract_inner_error(exc.value)
    assert inner.status_code == 400


def test_webhook_authentication_error_includes_status_code() -> None:
    """Invalid authentication should raise the dedicated error."""

    config = WebhookTriggerConfig(
        secret_header="x-secret",
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
        secret_header="x-secret",
        shared_secret="expected",
    )
    state = WebhookTriggerState(config)

    with pytest.raises(WebhookAuthenticationError):
        state.validate(make_request(headers={}))


def test_webhook_state_scrubs_shared_secret_header() -> None:
    """Shared secret headers should be removed before persisting metadata."""

    config = WebhookTriggerConfig(
        secret_header="x-secret",
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


def test_webhook_config_rejects_unsupported_hmac_algorithm() -> None:
    """Configuration should reject unsupported HMAC algorithms."""

    with pytest.raises(ValidationError) as exc:
        WebhookTriggerConfig(
            hmac_header="x-signature",
            hmac_secret="secret",
            hmac_algorithm="unsupported_algo",
        )

    inner = _extract_inner_error(exc.value)
    assert inner.status_code == 400
    assert "Unsupported HMAC algorithm" in str(inner)


@pytest.mark.parametrize(
    "config_kwargs",
    [
        {"hmac_header": "x-signature"},
        {"hmac_secret": "secret-value"},
    ],
)
def test_webhook_config_requires_hmac_pairs(config_kwargs: dict[str, str]) -> None:
    """HMAC header and secret must be provided together."""

    with pytest.raises(ValidationError) as exc:
        WebhookTriggerConfig(**config_kwargs)  # type: ignore[arg-type]

    inner = _extract_inner_error(exc.value)
    assert inner.status_code == 400
    assert "hmac_header and hmac_secret must be configured together" in str(inner)


def test_webhook_state_scrubs_hmac_signature_header() -> None:
    """HMAC signature headers should be removed before persisting metadata."""

    config = WebhookTriggerConfig(
        hmac_header="x-signature",
        hmac_secret="secret",
    )
    state = WebhookTriggerState(config)
    sanitized = state.scrub_headers_for_storage(
        {"x-signature": "abc123", "content-type": "application/json"}
    )

    assert "x-signature" not in sanitized
    assert sanitized["content-type"] == "application/json"


def test_webhook_shared_secret_validation_with_none_secret() -> None:
    """Shared secret validation should handle None secret gracefully."""

    config = WebhookTriggerConfig()
    state = WebhookTriggerState(config)
    state._config.shared_secret_header = "x-secret"
    state._config.shared_secret = None

    request = make_request(headers={"x-secret": "some-value"})

    with pytest.raises(WebhookAuthenticationError):
        state._validate_shared_secret(request)


def test_webhook_hmac_validation_with_none_header() -> None:
    """HMAC validation should handle None header name gracefully."""

    config = WebhookTriggerConfig()
    state = WebhookTriggerState(config)
    state._config.hmac_header = None
    state._config.hmac_secret = "secret"

    request = make_request(payload={"test": "data"})
    state._validate_hmac_signature(request)


def test_webhook_hmac_validation_missing_signature_header() -> None:
    """HMAC validation should reject requests missing the signature header."""

    config = WebhookTriggerConfig(
        hmac_header="x-signature",
        hmac_secret="secret",
    )
    state = WebhookTriggerState(config)

    request = make_request(payload={"test": "data"}, headers={})

    with pytest.raises(WebhookAuthenticationError):
        state.validate(request)


def test_webhook_hmac_without_timestamp_header() -> None:
    """HMAC validation should work without timestamp header."""

    secret = "super-secret"
    payload = {"foo": "bar"}
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    signature = hmac.new(
        secret.encode("utf-8"), payload_bytes, hashlib.sha256
    ).hexdigest()

    config = WebhookTriggerConfig(
        hmac_header="x-signature",
        hmac_secret=secret,
    )
    state = WebhookTriggerState(config)

    state.validate(
        make_request(
            payload=payload,
            headers={"x-signature": signature},
        )
    )


def test_webhook_canonical_payload_with_none() -> None:
    """Canonical payload bytes should handle None payload."""

    config = WebhookTriggerConfig()
    state = WebhookTriggerState(config)

    result = state._canonical_payload_bytes(None)
    assert result == b""


def test_webhook_canonical_payload_with_bytes() -> None:
    """Canonical payload bytes should pass through bytes unchanged."""

    config = WebhookTriggerConfig()
    state = WebhookTriggerState(config)

    payload = b"raw bytes"
    result = state._canonical_payload_bytes(payload)
    assert result == payload


def test_webhook_canonical_payload_with_string() -> None:
    """Canonical payload bytes should encode strings to UTF-8."""

    config = WebhookTriggerConfig()
    state = WebhookTriggerState(config)

    payload = "test string"
    result = state._canonical_payload_bytes(payload)
    assert result == b"test string"


def test_webhook_extract_hmac_signature_empty() -> None:
    """Signature extraction should reject empty strings."""

    config = WebhookTriggerConfig()
    state = WebhookTriggerState(config)

    with pytest.raises(WebhookAuthenticationError):
        state._extract_hmac_signature("")


def test_webhook_extract_hmac_signature_whitespace() -> None:
    """Signature extraction should reject whitespace-only strings."""

    config = WebhookTriggerConfig()
    state = WebhookTriggerState(config)

    with pytest.raises(WebhookAuthenticationError):
        state._extract_hmac_signature("   ")


def test_webhook_extract_hmac_signature_with_prefix() -> None:
    """Signature extraction should parse prefixed formats."""

    config = WebhookTriggerConfig()
    state = WebhookTriggerState(config)

    result = state._extract_hmac_signature("sha256=abc123def456")
    assert result == "abc123def456"

    result = state._extract_hmac_signature("v1=xyz789")
    assert result == "xyz789"

    result = state._extract_hmac_signature("signature=test_sig")
    assert result == "test_sig"


def test_webhook_extract_hmac_signature_empty_after_prefix() -> None:
    """Signature extraction should reject empty values after prefix."""

    config = WebhookTriggerConfig()
    state = WebhookTriggerState(config)

    with pytest.raises(WebhookAuthenticationError):
        state._extract_hmac_signature("sha256=")


def test_webhook_parse_timestamp_empty() -> None:
    """Timestamp parsing should reject empty strings."""

    config = WebhookTriggerConfig()
    state = WebhookTriggerState(config)

    with pytest.raises(WebhookAuthenticationError):
        state._parse_signature_timestamp("")


def test_webhook_parse_timestamp_whitespace() -> None:
    """Timestamp parsing should reject whitespace-only strings."""

    config = WebhookTriggerConfig()
    state = WebhookTriggerState(config)

    with pytest.raises(WebhookAuthenticationError):
        state._parse_signature_timestamp("   ")


def test_webhook_parse_timestamp_iso_format() -> None:
    """Timestamp parsing should support ISO format strings."""

    config = WebhookTriggerConfig(hmac_tolerance_seconds=600)
    state = WebhookTriggerState(config)

    now = datetime.now(tz=UTC)
    iso_string = now.isoformat().replace("+00:00", "Z")
    result = state._parse_signature_timestamp(iso_string)

    assert abs((result - now).total_seconds()) < 1


def test_webhook_parse_timestamp_with_zero_tolerance() -> None:
    """Timestamp parsing should skip tolerance check when tolerance is 0."""

    config = WebhookTriggerConfig(hmac_tolerance_seconds=0)
    state = WebhookTriggerState(config)

    old_timestamp = datetime.now(tz=UTC) - timedelta(seconds=1000)
    ts_value = str(int(old_timestamp.timestamp()))
    result = state._parse_signature_timestamp(ts_value)

    # Timestamp is parsed from integer seconds, so precision is lost
    assert abs((result - old_timestamp).total_seconds()) < 1


def test_webhook_replay_protection_purges_old_signatures() -> None:
    """Replay protection should purge signatures outside tolerance window."""

    config = WebhookTriggerConfig(
        hmac_header="x-signature",
        hmac_secret="secret",
        hmac_tolerance_seconds=1,
    )
    state = WebhookTriggerState(config)

    old_time = datetime.now(tz=UTC) - timedelta(seconds=10)
    state._recent_signatures.append(("old_sig", old_time))
    state._signature_cache.add("old_sig")

    state._enforce_signature_replay("new_sig", datetime.now(tz=UTC))

    assert "old_sig" not in state._signature_cache
    assert len(state._recent_signatures) == 1
    assert state._recent_signatures[0][0] == "new_sig"


def test_webhook_serialize_payload_with_bytes() -> None:
    """Payload serialization should decode bytes to UTF-8."""

    config = WebhookTriggerConfig()
    state = WebhookTriggerState(config)

    payload = b"test bytes"
    result = state.serialize_payload(payload)

    assert result == {"raw": "test bytes"}


def test_webhook_serialize_payload_with_dict() -> None:
    """Payload serialization should pass through non-bytes payloads."""

    config = WebhookTriggerConfig()
    state = WebhookTriggerState(config)

    payload = {"key": "value"}
    result = state.serialize_payload(payload)

    assert result == payload


def test_webhook_method_not_allowed_error() -> None:
    """MethodNotAllowedError should include allowed methods in message."""

    error = MethodNotAllowedError("DELETE", {"GET", "POST"})
    assert error.status_code == 405
    assert "DELETE" in str(error)
    assert "GET" in str(error) or "POST" in str(error)


def test_webhook_method_not_allowed_empty_set() -> None:
    """MethodNotAllowedError should handle empty allowed set."""

    error = MethodNotAllowedError("DELETE", set())
    assert error.status_code == 405
    assert "none" in str(error)


def test_webhook_method_validation_rejects_disallowed() -> None:
    """Request method validation should reject disallowed methods."""

    config = WebhookTriggerConfig(allowed_methods=["POST"])
    state = WebhookTriggerState(config)

    with pytest.raises(MethodNotAllowedError):
        state.validate(make_request(method="GET"))


def test_webhook_state_config_property() -> None:
    """State config property should return a deep copy."""

    config = WebhookTriggerConfig(allowed_methods=["POST"])
    state = WebhookTriggerState(config)

    retrieved = state.config
    retrieved.allowed_methods = ["GET", "PUT"]

    assert state.config.allowed_methods == ["POST"]


def test_webhook_state_update_config() -> None:
    """Updating config should replace state and clear rate limit data."""

    config1 = WebhookTriggerConfig(
        rate_limit=RateLimitConfig(limit=1, interval_seconds=60)
    )
    state = WebhookTriggerState(config1)

    state.validate(make_request())
    assert len(state._recent_invocations) == 1

    old_time = datetime.now(tz=UTC) - timedelta(seconds=10)
    state._recent_signatures.append(("sig1", old_time))
    state._signature_cache.add("sig1")

    config2 = WebhookTriggerConfig(allowed_methods=["GET"])
    state.update_config(config2)

    assert state.config.allowed_methods == ["GET"]
    assert len(state._recent_invocations) == 0
    assert len(state._recent_signatures) == 0
    assert len(state._signature_cache) == 0


def test_webhook_shared_secret_validation_missing_header() -> None:
    """Shared secret validation should handle missing provided header."""

    config = WebhookTriggerConfig(
        secret_header="x-secret",
        shared_secret="expected",
    )
    state = WebhookTriggerState(config)

    request = make_request(headers={})

    with pytest.raises(WebhookAuthenticationError):
        state._validate_shared_secret(request)


def test_webhook_extract_signature_with_complex_format() -> None:
    """Signature extraction should handle complex multi-part formats."""

    config = WebhookTriggerConfig()
    state = WebhookTriggerState(config)

    result = state._extract_hmac_signature("t=123,sha256=abc123,other=xyz")
    assert result == "abc123"

    result = state._extract_hmac_signature("timestamp=456,signature=def456")
    assert result == "def456"
