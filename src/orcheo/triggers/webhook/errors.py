"""Error types specific to webhook trigger processing."""

from __future__ import annotations


class WebhookValidationError(ValueError):
    """Base error raised when webhook requests fail validation."""

    def __init__(self, message: str, *, status_code: int) -> None:
        """Store the error message alongside the HTTP status code."""
        super().__init__(message)
        self.status_code = status_code


class MethodNotAllowedError(WebhookValidationError):
    """Raised when the inbound request method is not permitted."""

    def __init__(self, method: str, allowed: set[str]) -> None:
        """Initialize the error with the offending method and allowed set."""
        allowed_methods = ", ".join(sorted(allowed)) or "none"
        message = f"Method {method} not allowed. Allowed methods: {allowed_methods}"
        super().__init__(message, status_code=405)


class WebhookAuthenticationError(WebhookValidationError):
    """Raised when the request fails shared secret or HMAC validation."""

    def __init__(self) -> None:
        """Construct the error using a fixed authentication failure message."""
        super().__init__("Invalid webhook authentication credentials", status_code=401)


class RateLimitExceededError(WebhookValidationError):
    """Raised when requests exceed the configured rate limit."""

    def __init__(self, limit: int, interval_seconds: int) -> None:
        """Include the configured limit and interval in the error message."""
        message = (
            "Webhook rate limit exceeded. "
            f"Limit: {limit} requests per {interval_seconds} seconds"
        )
        super().__init__(message, status_code=429)


__all__ = [
    "WebhookValidationError",
    "MethodNotAllowedError",
    "WebhookAuthenticationError",
    "RateLimitExceededError",
]
