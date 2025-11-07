from __future__ import annotations
from datetime import UTC, datetime, timedelta
import pytest
from orcheo.triggers.webhook import (
    WebhookAuthenticationError,
    WebhookTriggerConfig,
    WebhookTriggerState,
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


def test_webhook_extract_signature_with_complex_format() -> None:
    """Signature extraction should handle complex multi-part formats."""

    config = WebhookTriggerConfig()
    state = WebhookTriggerState(config)

    result = state._extract_hmac_signature("t=123,sha256=abc123,other=xyz")
    assert result == "abc123"

    result = state._extract_hmac_signature("timestamp=456,signature=def456")
    assert result == "def456"


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
