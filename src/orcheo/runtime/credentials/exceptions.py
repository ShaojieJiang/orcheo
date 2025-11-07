"""Exception hierarchy for runtime credential resolution helpers."""

from __future__ import annotations


class CredentialResolutionError(RuntimeError):
    """Base error raised when credential placeholders cannot be resolved."""


class CredentialResolverUnavailableError(CredentialResolutionError):
    """Raised when placeholders are used without an active resolver in scope."""


class CredentialReferenceNotFoundError(CredentialResolutionError):
    """Raised when a referenced credential cannot be located in the vault."""


class DuplicateCredentialReferenceError(CredentialResolutionError):
    """Raised when a reference matches multiple credentials."""


class UnknownCredentialPayloadError(CredentialResolutionError):
    """Raised when a placeholder requests an unsupported payload path."""
