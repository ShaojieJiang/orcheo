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
    CredentialCipher,
    CredentialMetadata,
)


class VaultError(RuntimeError):
    """Base error type for vault operations."""


class CredentialNotFoundError(VaultError):
    """Raised when a credential cannot be found for the workflow."""


class WorkflowScopeError(VaultError):
    """Raised when attempting to access a credential from another workflow."""


class RotationPolicyError(VaultError):
    """Raised when a rotation violates configured policies."""


class BaseCredentialVault:
    """Base helper that implements common credential vault workflows."""

    def __init__(self, *, cipher: CredentialCipher | None = None) -> None:
        """Initialize the vault with an encryption cipher."""
        self._cipher = cipher or AesGcmCredentialCipher(key=secrets.token_hex(32))

    def create_credential(
        self,
        *,
        workflow_id: UUID,
        name: str,
        provider: str,
        scopes: Sequence[str],
        secret: str,
        actor: str,
    ) -> CredentialMetadata:
        """Encrypt and persist a new credential."""
        metadata = CredentialMetadata.create(
            workflow_id=workflow_id,
            name=name,
            provider=provider,
            scopes=scopes,
            secret=secret,
            cipher=self._cipher,
            actor=actor,
        )
        self._persist_metadata(metadata)
        return metadata.model_copy(deep=True)

    def rotate_secret(
        self,
        *,
        workflow_id: UUID,
        credential_id: UUID,
        secret: str,
        actor: str,
    ) -> CredentialMetadata:
        """Rotate an existing credential secret enforcing policy constraints."""
        metadata = self._get_metadata(
            workflow_id=workflow_id, credential_id=credential_id
        )
        current_secret = metadata.reveal(cipher=self._cipher)
        if current_secret == secret:
            msg = "Rotated secret must differ from the previous value."
            raise RotationPolicyError(msg)
        metadata.rotate_secret(secret=secret, cipher=self._cipher, actor=actor)
        self._persist_metadata(metadata)
        return metadata.model_copy(deep=True)

    def reveal_secret(self, *, workflow_id: UUID, credential_id: UUID) -> str:
        """Return the decrypted secret for the credential."""
        metadata = self._get_metadata(
            workflow_id=workflow_id, credential_id=credential_id
        )
        return metadata.reveal(cipher=self._cipher)

    def list_credentials(self, *, workflow_id: UUID) -> list[CredentialMetadata]:
        """Return credential metadata for a workflow."""
        return [item.model_copy(deep=True) for item in self._iter_metadata(workflow_id)]

    def describe_credentials(
        self, *, workflow_id: UUID
    ) -> list[MutableMapping[str, object]]:
        """Return masked representations suitable for logging."""
        return [item.redact() for item in self._iter_metadata(workflow_id)]

    def _get_metadata(
        self, *, workflow_id: UUID, credential_id: UUID
    ) -> CredentialMetadata:
        metadata = self._load_metadata(credential_id)
        if metadata.workflow_id != workflow_id:
            msg = "Credential does not belong to the provided workflow."
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

    def _iter_metadata(
        self, workflow_id: UUID
    ) -> Iterable[CredentialMetadata]:  # pragma: no cover
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

    def _iter_metadata(self, workflow_id: UUID) -> Iterable[CredentialMetadata]:
        for metadata in self._store.values():
            if metadata.workflow_id == workflow_id:
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
                    str(metadata.workflow_id),
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

    def _iter_metadata(self, workflow_id: UUID) -> Iterable[CredentialMetadata]:
        with self._lock, sqlite3.connect(self._path) as conn:
            cursor = conn.execute(
                """
                SELECT payload
                  FROM credentials
                 WHERE workflow_id = ?
              ORDER BY created_at ASC
                """,
                (str(workflow_id),),
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
