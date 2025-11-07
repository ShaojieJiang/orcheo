from __future__ import annotations
from collections import deque
from datetime import UTC, datetime, timedelta
from fastapi import status
from .errors import AuthenticationError


class SlidingWindowRateLimiter:
    """Maintain a sliding window rate limiter for authentication events."""

    def __init__(
        self,
        limit: int,
        interval_seconds: int,
        *,
        code: str,
        message_template: str,
    ) -> None:
        """Configure the limiter with bounds, window interval, and error metadata."""
        self._limit = max(int(limit), 0)
        self._interval = max(int(interval_seconds), 1)
        self._code = code
        self._message_template = message_template
        self._events: dict[str, deque[datetime]] = {}

    def hit(self, key: str, *, now: datetime | None = None) -> None:
        """Record an attempt and raise when the limit is exceeded."""
        if self._limit == 0 or not key:
            return

        timestamp = now or datetime.now(tz=UTC)
        window_start = timestamp - timedelta(seconds=self._interval)
        bucket = self._events.setdefault(key, deque())

        while bucket and bucket[0] <= window_start:
            bucket.popleft()

        if len(bucket) >= self._limit:
            message = self._message_template.format(
                key=key, limit=self._limit, interval=self._interval
            )
            raise AuthenticationError(
                message,
                code=self._code,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(self._interval)},
            )

        bucket.append(timestamp)

    def reset(self) -> None:
        """Clear stored rate limiting state."""
        self._events.clear()


class AuthRateLimiter:
    """Aggregate rate limiting for per-IP and per-identity enforcement."""

    def __init__(
        self, *, ip_limit: int, identity_limit: int, interval_seconds: int
    ) -> None:
        """Configure rate limits for per-IP and per-identity buckets."""
        self._ip = SlidingWindowRateLimiter(
            ip_limit,
            interval_seconds,
            code="auth.rate_limited.ip",
            message_template="Too many authentication attempts from IP {key}",
        )
        self._identity = SlidingWindowRateLimiter(
            identity_limit,
            interval_seconds,
            code="auth.rate_limited.identity",
            message_template="Too many authentication attempts for identity {key}",
        )

    def check_ip(self, ip: str | None, *, now: datetime | None = None) -> None:
        """Enforce the configured rate limit for an IP address."""
        if ip:
            self._ip.hit(ip, now=now)

    def check_identity(
        self, identity: str | None, *, now: datetime | None = None
    ) -> None:
        """Enforce the configured rate limit for an authenticated identity."""
        if identity:
            self._identity.hit(identity, now=now)

    def reset(self) -> None:
        """Reset internal counters for both limiters."""
        self._ip.reset()
        self._identity.reset()
