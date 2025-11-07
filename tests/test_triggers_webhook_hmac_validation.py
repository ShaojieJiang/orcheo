from __future__ import annotations
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
import pytest
from orcheo.triggers.webhook import (
    WebhookAuthenticationError,
    WebhookTriggerConfig,
    WebhookTriggerState,
)
from tests.triggers_webhook_helpers import make_request, sign_payload


def test_webhook_validates_hmac_signature() -> None:
    """Valid HMAC signatures should be accepted."""

    secret = "super-secret"
    algorithm = "sha256"
    payload = {"foo": "bar", "count": 3}
    timestamp = datetime.now(tz=UTC)
    signature, ts_value = sign_payload(
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
    signature, ts_value = sign_payload(
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

    # Ensure mutated signature is always different so the test is deterministic.
    invalid_signature = signature[:-1] + ("0" if signature[-1] != "0" else "1")

    with pytest.raises(WebhookAuthenticationError):
        state.validate(
            make_request(
                payload=payload,
                headers={
                    "x-signature": invalid_signature,
                    "x-signature-ts": ts_value,
                },
            )
        )


def test_webhook_hmac_requires_timestamp_when_configured() -> None:
    """Timestamp header must be present when configured for HMAC verification."""

    secret = "super-secret"
    payload = {"foo": "bar"}
    signature, _ = sign_payload(payload, secret=secret)

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
    signature, ts_value = sign_payload(
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
    signature, ts_value = sign_payload(
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
