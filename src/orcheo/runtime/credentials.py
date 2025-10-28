"""Runtime helpers for resolving credential placeholders during execution."""

from __future__ import annotations
import re
from collections.abc import Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from orcheo.models import (
    CredentialAccessContext,
    CredentialKind,
    CredentialMetadata,
    OAuthTokenSecrets,
)
from orcheo.vault import BaseCredentialVault, CredentialNotFoundError


_PLACEHOLDER_PATTERN = re.compile(r"^\[\[(?P<body>.+)\]\]$")
_ACTIVE_RESOLVER: ContextVar[CredentialResolver | None] = ContextVar(
    "orcheo_active_credential_resolver", default=None
)


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


@dataclass(frozen=True, slots=True)
class CredentialReference:
    """Opaque descriptor pointing to a credential payload."""

    identifier: str
    payload_path: tuple[str, ...] = ("secret",)

    @classmethod
    def from_placeholder(cls, value: str) -> CredentialReference | None:
        """Return a reference extracted from a ``[[credential]]`` placeholder."""
        match = _PLACEHOLDER_PATTERN.fullmatch(value.strip())
        if not match:
            return None
        body = match.group("body").strip()
        if not body:
            return None
        identifier, payload = _split_placeholder_body(body)
        if not identifier:
            return None
        if not payload:
            payload = ("secret",)
        return cls(identifier=identifier, payload_path=payload)


def _split_placeholder_body(body: str) -> tuple[str, tuple[str, ...]]:
    """Split a placeholder body into identifier and payload path."""
    if "#" not in body:
        return body, ()
    identifier, raw_path = body.split("#", 1)
    path_parts = tuple(part.strip() for part in raw_path.split(".") if part.strip())
    return identifier.strip(), path_parts


def credential_ref(
    identifier: str,
    payload: str | Iterable[str] = "secret",
) -> CredentialReference:
    """Return a :class:`CredentialReference` for Python-authored graphs."""
    normalized_identifier = identifier.strip()
    if not normalized_identifier:
        msg = "Credential identifier must be a non-empty string"
        raise ValueError(msg)
    if isinstance(payload, str):
        payload_parts = tuple(
            part.strip() for part in payload.split(".") if part.strip()
        )
    else:
        payload_parts = tuple(
            str(part).strip() for part in payload if str(part).strip()
        )
    if not payload_parts:
        payload_parts = ("secret",)
    return CredentialReference(
        identifier=normalized_identifier,
        payload_path=payload_parts,
    )


def parse_credential_reference(value: str) -> CredentialReference | None:
    """Return a credential reference encoded within the provided string."""
    return CredentialReference.from_placeholder(value)


@contextmanager
def credential_resolution(
    resolver: CredentialResolver | None,
) -> Any:
    """Install ``resolver`` for the duration of the context manager."""
    if resolver is None:
        yield None
        return
    token = _ACTIVE_RESOLVER.set(resolver)
    try:
        yield resolver
    finally:
        _ACTIVE_RESOLVER.reset(token)


def get_active_credential_resolver() -> CredentialResolver | None:
    """Return the credential resolver currently bound to the execution context."""
    return _ACTIVE_RESOLVER.get()


class CredentialResolver:
    """Resolve credential references against a vault with per-run caching."""

    def __init__(
        self,
        vault: BaseCredentialVault,
        *,
        context: CredentialAccessContext | None = None,
    ) -> None:
        """Create a resolver bound to ``vault`` and an optional access context."""
        self._vault = vault
        self._context = context
        self._metadata_by_id: dict[UUID, CredentialMetadata] | None = None
        self._metadata_by_name: dict[str, list[CredentialMetadata]] | None = None
        self._secret_cache: dict[UUID, Any] = {}
        self._oauth_cache: dict[UUID, OAuthTokenSecrets | None] = {}

    def resolve(self, reference: CredentialReference) -> Any:
        """Return the concrete payload referenced by ``reference``."""
        metadata = self._locate_metadata(reference.identifier)
        return self._extract_payload(metadata, reference.payload_path)

    def _locate_metadata(self, identifier: str) -> CredentialMetadata:
        metadata_by_id, metadata_by_name = self._load_metadata_index()
        try:
            credential_id = UUID(identifier)
        except ValueError:
            credential_id = None

        if credential_id is not None:
            metadata = metadata_by_id.get(credential_id)
            if metadata is not None:
                return metadata

        normalized = identifier.strip()
        matches = metadata_by_name.get(normalized, []) if metadata_by_name else []
        if not matches:
            msg = f"Credential '{identifier}' was not found in the configured vault"
            raise CredentialReferenceNotFoundError(msg)
        if len(matches) > 1:
            msg = (
                "Multiple credentials share the name "
                f"'{identifier}'. Use the credential UUID instead."
            )
            raise DuplicateCredentialReferenceError(msg)
        return matches[0]

    def _load_metadata_index(
        self,
    ) -> tuple[dict[UUID, CredentialMetadata], dict[str, list[CredentialMetadata]]]:
        if self._metadata_by_id is not None and self._metadata_by_name is not None:
            return self._metadata_by_id, self._metadata_by_name
        try:
            metadata_items = self._vault.list_credentials(context=self._context)
        except CredentialNotFoundError as exc:  # pragma: no cover - defensive
            raise CredentialReferenceNotFoundError(str(exc)) from exc
        by_id: dict[UUID, CredentialMetadata] = {}
        by_name: dict[str, list[CredentialMetadata]] = {}
        for metadata in metadata_items:
            by_id[metadata.id] = metadata
            by_name.setdefault(metadata.name, []).append(metadata)
        self._metadata_by_id = by_id
        self._metadata_by_name = by_name
        return by_id, by_name

    def _extract_payload(
        self, metadata: CredentialMetadata, payload_path: tuple[str, ...]
    ) -> Any:
        if not payload_path:
            return self._resolve_secret(metadata)
        head, *tail = payload_path
        if head.lower() == "secret":
            if tail:
                msg = "Secret payload does not support nested attributes"
                raise UnknownCredentialPayloadError(msg)
            return self._resolve_secret(metadata)
        if head.lower() == "oauth":
            tokens = self._resolve_oauth_tokens(metadata)
            if tokens is None:
                return None
            if not tail:
                return tokens.model_copy(deep=True)
            current: Any = tokens
            for attribute in tail:
                if not hasattr(current, attribute):
                    available = [
                        attr
                        for attr in ("access_token", "refresh_token", "expires_at")
                        if hasattr(current, attr)
                    ]
                    available_list = ", ".join(available) or "<none>"
                    msg = (
                        "OAuth token payload does not expose attribute "
                        f"'{attribute}'. Available: {available_list}"
                    )
                    raise UnknownCredentialPayloadError(msg)
                current = getattr(current, attribute)
            return current
        msg = (
            "Credential placeholder requested unsupported payload segment "
            f"'{payload_path[0]}'"
        )
        raise UnknownCredentialPayloadError(msg)

    def _resolve_secret(self, metadata: CredentialMetadata) -> Any:
        cached = self._secret_cache.get(metadata.id)
        if cached is not None:
            return cached
        secret = self._vault.reveal_secret(
            credential_id=metadata.id, context=self._context
        )
        self._secret_cache[metadata.id] = secret
        return secret

    def _resolve_oauth_tokens(
        self, metadata: CredentialMetadata
    ) -> OAuthTokenSecrets | None:
        if metadata.kind is not CredentialKind.OAUTH:
            msg = "OAuth payload requested for credential that is not of kind 'oauth'"
            raise UnknownCredentialPayloadError(msg)
        cached = self._oauth_cache.get(metadata.id)
        if cached is not None:
            return cached.model_copy(deep=True)
        tokens = metadata.reveal_oauth_tokens(cipher=self._vault.cipher)
        self._oauth_cache[metadata.id] = tokens
        if tokens is None:
            return None
        return tokens.model_copy(deep=True)
