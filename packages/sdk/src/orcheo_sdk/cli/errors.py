"""Error types raised by the Orcheo CLI."""

from __future__ import annotations


class CLIError(RuntimeError):
    """Base error raised for CLI failures."""


class CLIConfigurationError(CLIError):
    """Raised when the CLI configuration is invalid or incomplete."""


class APICallError(CLIError):
    """Raised when an API interaction fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        """Store the message and optional HTTP status code."""
        super().__init__(message)
        self.status_code = status_code
