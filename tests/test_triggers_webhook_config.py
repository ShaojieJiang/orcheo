from __future__ import annotations
from datetime import UTC, datetime, timedelta
import pytest
from pydantic import ValidationError
from orcheo.triggers.webhook import (
    MethodNotAllowedError,
    RateLimitConfig,
    WebhookTriggerConfig,
    WebhookTriggerState,
)
from tests.triggers_webhook_helpers import extract_inner_error, make_request


def test_webhook_config_rejects_empty_methods() -> None:
    """Webhook configuration must allow at least one HTTP method."""

    with pytest.raises(ValidationError) as exc:
        WebhookTriggerConfig(allowed_methods=[])

    inner = extract_inner_error(exc.value)
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

    inner = extract_inner_error(exc.value)
    assert inner.status_code == 400


def test_webhook_config_rejects_unsupported_hmac_algorithm() -> None:
    """Configuration should reject unsupported HMAC algorithms."""

    with pytest.raises(ValidationError) as exc:
        WebhookTriggerConfig(
            hmac_header="x-signature",
            hmac_secret="secret",
            hmac_algorithm="unsupported_algo",
        )

    inner = extract_inner_error(exc.value)
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

    inner = extract_inner_error(exc.value)
    assert inner.status_code == 400
    assert "hmac_header and hmac_secret must be configured together" in str(inner)


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
