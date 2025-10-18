"""Credential vault implementations with AES-256 encryption support."""

from __future__ import annotations
import secrets
import sqlite3
import threading
from collections.abc import Iterable, MutableMapping, Sequence
from pathlib import Path
from uuid import UUID
from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialCipher,
    CredentialHealthStatus,
    CredentialKind,
    CredentialMetadata,
    CredentialScope,
    OAuthTokenSecrets,
)


class VaultError(RuntimeError):
    """Base error type for vault operations."""


class CredentialNotFoundError(VaultError):
    """Raised when a credential cannot be found for the workflow."""


class WorkflowScopeError(VaultError):
    """Raised when a credential scope denies access for the provided context."""


class RotationPolicyError(VaultError):
    """Raised when a rotation violates configured policies."""


class BaseCredentialVault:
    """Base helper that implements common credential vault workflows."""

    def __init__(self, *, cipher: CredentialCipher | None = None) -> None:
        """Initialize the vault with an encryption cipher."""
        self._cipher = cipher or AesGcmCredentialCipher(key=secrets.token_hex(32))

    @property
    def cipher(self) -> CredentialCipher:
        """Expose the credential cipher for services that need direct access."""
        return self._cipher

    def create_credential(
        self,
        *,
        name: str,
        provider: str,
        scopes: Sequence[str],
        secret: str,
        actor: str,
        scope: CredentialScope | None = None,
        kind: CredentialKind | str = CredentialKind.SECRET,
        oauth_tokens: OAuthTokenSecrets | None = None,
    ) -> CredentialMetadata:
        """Encrypt and persist a new credential."""
        if not isinstance(kind, CredentialKind):
            kind = CredentialKind(str(kind))
        metadata = CredentialMetadata.create(
            name=name,
            provider=provider,
            scopes=scopes,
            secret=secret,
            cipher=self._cipher,
            actor=actor,
            scope=scope,
            kind=kind,
            oauth_tokens=oauth_tokens,
        )
        self._persist_metadata(metadata)
        return metadata.model_copy(deep=True)

    def rotate_secret(
        self,
        *,
        credential_id: UUID,
        secret: str,
        actor: str,
        context: CredentialAccessContext | None = None,
    ) -> CredentialMetadata:
        """Rotate an existing credential secret enforcing policy constraints."""
        metadata = self._get_metadata(credential_id=credential_id, context=context)
        current_secret = metadata.reveal(cipher=self._cipher)
        if current_secret == secret:
            msg = "Rotated secret must differ from the previous value."
            raise RotationPolicyError(msg)
        metadata.rotate_secret(secret=secret, cipher=self._cipher, actor=actor)
        self._persist_metadata(metadata)
        return metadata.model_copy(deep=True)

    def update_oauth_tokens(
        self,
        *,
        credential_id: UUID,
        tokens: OAuthTokenSecrets | None,
        actor: str | None = None,
        context: CredentialAccessContext | None = None,
    ) -> CredentialMetadata:
        """Update OAuth tokens associated with the credential."""
        metadata = self._get_metadata(credential_id=credential_id, context=context)
        metadata.update_oauth_tokens(
            cipher=self._cipher, tokens=tokens, actor=actor or "system"
        )
        self._persist_metadata(metadata)
        return metadata.model_copy(deep=True)

    def mark_health(
        self,
        *,
        credential_id: UUID,
        status: CredentialHealthStatus,
        reason: str | None,
        actor: str | None = None,
        context: CredentialAccessContext | None = None,
    ) -> CredentialMetadata:
        """Persist the latest health evaluation result for the credential."""
        metadata = self._get_metadata(credential_id=credential_id, context=context)
        metadata.mark_health(status=status, reason=reason, actor=actor)
        self._persist_metadata(metadata)
        return metadata.model_copy(deep=True)

    def reveal_secret(
        self,
        *,
        credential_id: UUID,
        context: CredentialAccessContext | None = None,
    ) -> str:
        """Return the decrypted secret for the credential."""
        metadata = self._get_metadata(credential_id=credential_id, context=context)
        return metadata.reveal(cipher=self._cipher)

    def list_credentials(
        self, *, context: CredentialAccessContext | None = None
    ) -> list[CredentialMetadata]:
        """Return credential metadata for a workflow."""
        access_context = context or CredentialAccessContext()
        return [
            item.model_copy(deep=True)
            for item in self._iter_metadata()
            if item.scope.allows(access_context)
        ]

    def describe_credentials(
        self, *, context: CredentialAccessContext | None = None
    ) -> list[MutableMapping[str, object]]:
        """Return masked representations suitable for logging."""
        access_context = context or CredentialAccessContext()
        return [
            item.redact()
            for item in self._iter_metadata()
            if item.scope.allows(access_context)
        ]

    def _get_metadata(
        self,
        *,
        credential_id: UUID,
        context: CredentialAccessContext | None = None,
    ) -> CredentialMetadata:
        metadata = self._load_metadata(credential_id)
        access_context = context or CredentialAccessContext()
        if not metadata.scope.allows(access_context):
            msg = "Credential cannot be accessed with the provided context."
            raise WorkflowScopeError(msg)
        return metadata

    def _persist_metadata(
        self, metadata: CredentialMetadata
    ) -> None:  # pragma: no cover
        raise NotImplementedError

    def _load_metadata(
        self, credential_id: UUID
    ) -> CredentialMetadata:  # pragma: no cover
        raise NotImplementedError

    def _iter_metadata(self) -> Iterable[CredentialMetadata]:  # pragma: no cover
        raise NotImplementedError


class InMemoryCredentialVault(BaseCredentialVault):
    """In-memory credential vault used for tests and local workflows."""

    def __init__(self, *, cipher: CredentialCipher | None = None) -> None:
        """Create an ephemeral in-memory vault instance."""
        super().__init__(cipher=cipher)
        self._store: dict[UUID, CredentialMetadata] = {}

    def _persist_metadata(self, metadata: CredentialMetadata) -> None:
        self._store[metadata.id] = metadata.model_copy(deep=True)

    def _load_metadata(self, credential_id: UUID) -> CredentialMetadata:
        try:
            return self._store[credential_id].model_copy(deep=True)
        except KeyError as exc:
            msg = "Credential was not found."
            raise CredentialNotFoundError(msg) from exc

    def _iter_metadata(self) -> Iterable[CredentialMetadata]:
        for metadata in self._store.values():
            yield metadata.model_copy(deep=True)


class FileCredentialVault(BaseCredentialVault):
    """File-backed credential vault stored in a SQLite database."""

    def __init__(
        self, path: str | Path, *, cipher: CredentialCipher | None = None
    ) -> None:
        """Create a SQLite-backed credential vault."""
        super().__init__(cipher=cipher)
        self._path = Path(path).expanduser()
        self._lock = threading.Lock()
        self._initialize()

    def _initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS credentials (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_credentials_workflow
                    ON credentials(workflow_id)
                """
            )
            conn.commit()

    def _persist_metadata(self, metadata: CredentialMetadata) -> None:
        payload = metadata.model_dump_json()
        with self._lock, sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO credentials (
                    id,
                    workflow_id,
                    name,
                    provider,
                    created_at,
                    updated_at,
                    payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(metadata.id),
                    metadata.scope.scope_hint(),
                    metadata.name,
                    metadata.provider,
                    metadata.created_at.isoformat(),
                    metadata.updated_at.isoformat(),
                    payload,
                ),
            )
            conn.commit()

    def _load_metadata(self, credential_id: UUID) -> CredentialMetadata:
        with self._lock, sqlite3.connect(self._path) as conn:
            cursor = conn.execute(
                "SELECT payload FROM credentials WHERE id = ?",
                (str(credential_id),),
            )
            row = cursor.fetchone()
        if row is None:
            msg = "Credential was not found."
            raise CredentialNotFoundError(msg)
        return CredentialMetadata.model_validate_json(row[0])

    def _iter_metadata(self) -> Iterable[CredentialMetadata]:
        with self._lock, sqlite3.connect(self._path) as conn:
            cursor = conn.execute(
                """
                SELECT payload
                  FROM credentials
              ORDER BY created_at ASC
                """
            )
            rows = cursor.fetchall()
        for row in rows:
            yield CredentialMetadata.model_validate_json(row[0])


__all__ = [
    "VaultError",
    "CredentialNotFoundError",
    "WorkflowScopeError",
    "RotationPolicyError",
    "BaseCredentialVault",
    "InMemoryCredentialVault",
    "FileCredentialVault",
]
