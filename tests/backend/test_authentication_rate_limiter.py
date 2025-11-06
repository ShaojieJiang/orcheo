"""Rate limiter tests split from the extended suite."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
import pytest
from tests.backend.authentication_test_utils import reset_auth_state


@pytest.fixture(autouse=True)
def _reset_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure authentication state is cleared between tests."""

    yield from reset_auth_state(monkeypatch)


def test_sliding_window_rate_limiter_clears_old_events() -> None:
    """SlidingWindowRateLimiter removes old events outside the window."""
    from orcheo_backend.app.authentication import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter(3, 1, code="test", message_template="Test {key}")
    now = datetime.now(tz=UTC)

    # Add events at different times
    limiter.hit("key1", now=now - timedelta(seconds=2))
    limiter.hit("key1", now=now - timedelta(seconds=1.5))
    limiter.hit("key1", now=now)

    # Old events should be removed, so this shouldn't raise
    limiter.hit("key1", now=now)


def test_get_auth_rate_limiter_refresh() -> None:
    """get_auth_rate_limiter refreshes when requested."""
    from orcheo_backend.app.authentication import get_auth_rate_limiter

    limiter1 = get_auth_rate_limiter()
    limiter2 = get_auth_rate_limiter(refresh=True)

    # Should create new instance
    assert limiter1 is not limiter2


def test_auth_rate_limiter_reset() -> None:
    """AuthRateLimiter.reset clears both IP and identity limiters."""
    from orcheo_backend.app.authentication import AuthRateLimiter

    limiter = AuthRateLimiter(ip_limit=2, identity_limit=2, interval_seconds=60)

    limiter.check_ip("1.2.3.4")
    limiter.check_identity("user-1")

    limiter.reset()

    # Should be able to use again after reset
    limiter.check_ip("1.2.3.4")
    limiter.check_identity("user-1")


def test_auth_rate_limiter_check_with_none_values() -> None:
    """AuthRateLimiter handles None IP and identity gracefully."""
    from orcheo_backend.app.authentication import AuthRateLimiter

    limiter = AuthRateLimiter(ip_limit=2, identity_limit=2, interval_seconds=60)

    # Should not raise
    limiter.check_ip(None)
    limiter.check_identity(None)
