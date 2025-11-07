"""Sliding window and auth rate limiter unit tests."""

from __future__ import annotations
import pytest
from orcheo_backend.app.authentication import (
    AuthenticationError,
    AuthRateLimiter,
    SlidingWindowRateLimiter,
)


def test_sliding_window_rate_limiter_disabled_when_limit_zero() -> None:
    """Rate limiter does not enforce when limit is 0."""

    limiter = SlidingWindowRateLimiter(
        0, 60, code="test", message_template="Test {key}"
    )

    # Should not raise
    for _ in range(100):
        limiter.hit("test-key")


def test_sliding_window_rate_limiter_ignores_empty_key() -> None:
    """Rate limiter does not enforce when key is empty."""

    limiter = SlidingWindowRateLimiter(
        5, 60, code="test", message_template="Test {key}"
    )

    # Should not raise
    for _ in range(100):
        limiter.hit("")


def test_sliding_window_rate_limiter_reset() -> None:
    """reset() clears internal state."""

    limiter = SlidingWindowRateLimiter(
        2, 60, code="test", message_template="Test {key}"
    )

    limiter.hit("test-key")
    limiter.hit("test-key")

    limiter.reset()

    # Should not raise after reset
    limiter.hit("test-key")
    limiter.hit("test-key")


def test_auth_rate_limiter_check_ip_and_identity() -> None:
    """AuthRateLimiter checks both IP and identity limits."""

    limiter = AuthRateLimiter(ip_limit=2, identity_limit=2, interval_seconds=60)

    # IP limiting
    limiter.check_ip("1.2.3.4")
    limiter.check_ip("1.2.3.4")

    with pytest.raises(AuthenticationError) as exc:
        limiter.check_ip("1.2.3.4")
    assert exc.value.code == "auth.rate_limited.ip"

    # Identity limiting
    limiter.reset()
    limiter.check_identity("user-1")
    limiter.check_identity("user-1")

    with pytest.raises(AuthenticationError) as exc:
        limiter.check_identity("user-1")
    assert exc.value.code == "auth.rate_limited.identity"
