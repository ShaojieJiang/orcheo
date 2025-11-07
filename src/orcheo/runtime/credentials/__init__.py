"""Runtime helpers for resolving credential placeholders during execution."""

from .context import credential_resolution, get_active_credential_resolver
from .exceptions import (
    CredentialReferenceNotFoundError,
    CredentialResolutionError,
    CredentialResolverUnavailableError,
    DuplicateCredentialReferenceError,
    UnknownCredentialPayloadError,
)
from .references import (
    CredentialReference,
    credential_ref,
    parse_credential_reference,
)
from .resolver import CredentialResolver


__all__ = [
    "CredentialReference",
    "CredentialReferenceNotFoundError",
    "CredentialResolutionError",
    "CredentialResolver",
    "CredentialResolverUnavailableError",
    "DuplicateCredentialReferenceError",
    "UnknownCredentialPayloadError",
    "credential_ref",
    "credential_resolution",
    "get_active_credential_resolver",
    "parse_credential_reference",
]
