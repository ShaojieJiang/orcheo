from __future__ import annotations
from datetime import UTC, datetime, timedelta
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
