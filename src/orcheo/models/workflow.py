"""Workflow-centric domain models with encryption and audit hooks."""

from __future__ import annotations
import hashlib
import json
import re
from base64 import urlsafe_b64encode
from collections.abc import Mapping, MutableMapping, Sequence
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol
from uuid import UUID, uuid4
from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(tz=UTC)


def _slugify(value: str) -> str:
    """Convert the provided value into a workflow-safe slug."""
    normalized = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return normalized or value.strip().lower() or str(uuid4())


class OrcheoBaseModel(BaseModel):
    """Base model that enforces Orcheo validation defaults."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AuditRecord(OrcheoBaseModel):
    """Single audit event describing actor, action, and context."""

    actor: str
    action: str
    at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimestampedAuditModel(OrcheoBaseModel):
    """Base class for entities that track timestamps and audit logs."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    audit_log: list[AuditRecord] = Field(default_factory=list)

    def record_event(
        self,
        *,
        actor: str,
        action: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> AuditRecord:
        """Append an audit entry and update the modification timestamp."""
        entry = AuditRecord(
            actor=actor,
            action=action,
            metadata=dict(metadata or {}),
        )
        self.audit_log.append(entry)
        self.updated_at = entry.at
        return entry


class Workflow(TimestampedAuditModel):
    """Represents a workflow container with metadata and audit trail."""

    name: str
    slug: str = ""
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_archived: bool = False

    @field_validator("tags", mode="after")
    @classmethod
    def _dedupe_tags(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for tag in value:
            normalized = tag.strip()
            key = normalized.lower()
            if key and key not in seen:
                seen.add(key)
                deduped.append(key)
        return deduped

    @model_validator(mode="after")
    def _populate_slug(self) -> Workflow:
        slug_source = self.slug or self.name
        if not slug_source:
            msg = "Workflow requires a name or slug to be provided."
            raise ValueError(msg)
        object.__setattr__(self, "slug", _slugify(slug_source))
        return self


class WorkflowVersion(TimestampedAuditModel):
    """Versioned definition of a workflow graph."""

    workflow_id: UUID
    version: int = Field(gt=0)
    graph: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str
    notes: str | None = None

    def compute_checksum(self) -> str:
        """Return a deterministic checksum for the graph definition."""
        serialized = json.dumps(self.graph, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class WorkflowRunStatus(str, Enum):
    """Possible states for an individual workflow execution run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """Return whether the status represents a terminal state."""
        return self in {
            WorkflowRunStatus.SUCCEEDED,
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.CANCELLED,
        }


class WorkflowRun(TimestampedAuditModel):
    """Runtime record for a workflow execution."""

    workflow_version_id: UUID
    status: WorkflowRunStatus = Field(default=WorkflowRunStatus.PENDING)
    triggered_by: str
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

    def mark_started(self, *, actor: str) -> None:
        """Transition the run into the running state."""
        if self.status is not WorkflowRunStatus.PENDING:
            msg = "Only pending runs can be started."
            raise ValueError(msg)
        self.status = WorkflowRunStatus.RUNNING
        self.started_at = _utcnow()
        self.record_event(actor=actor, action="run_started")

    def mark_succeeded(
        self,
        *,
        actor: str,
        output: Mapping[str, Any] | None = None,
    ) -> None:
        """Mark the run as successfully completed."""
        if self.status is not WorkflowRunStatus.RUNNING:
            msg = "Only running runs can be marked as succeeded."
            raise ValueError(msg)
        self.status = WorkflowRunStatus.SUCCEEDED
        self.completed_at = _utcnow()
        self.output_payload = dict(output or {})
        self.error = None
        self.record_event(actor=actor, action="run_succeeded")

    def mark_failed(self, *, actor: str, error: str) -> None:
        """Mark the run as failed with the provided error message."""
        if self.status not in {WorkflowRunStatus.PENDING, WorkflowRunStatus.RUNNING}:
            msg = "Only pending or running runs can be marked as failed."
            raise ValueError(msg)
        self.status = WorkflowRunStatus.FAILED
        self.completed_at = _utcnow()
        self.error = error
        self.record_event(actor=actor, action="run_failed", metadata={"error": error})

    def mark_cancelled(self, *, actor: str, reason: str | None = None) -> None:
        """Cancel the run from a non-terminal state."""
        if self.status.is_terminal:
            msg = "Cannot cancel a run that is already completed."
            raise ValueError(msg)
        self.status = WorkflowRunStatus.CANCELLED
        self.completed_at = _utcnow()
        self.error = reason
        metadata: dict[str, Any] = {}
        if reason:
            metadata["reason"] = reason
        self.record_event(actor=actor, action="run_cancelled", metadata=metadata)


class CredentialCipher(Protocol):
    """Protocol describing encryption strategies for credential secrets."""

    algorithm: str
    key_id: str

    def encrypt(self, plaintext: str) -> EncryptionEnvelope:
        """Return an envelope containing ciphertext for the plaintext secret."""

    def decrypt(self, envelope: EncryptionEnvelope) -> str:
        """Decrypt the provided envelope and return the plaintext secret."""


class EncryptionEnvelope(OrcheoBaseModel):
    """Encrypted payload metadata produced by a :class:`CredentialCipher`."""

    algorithm: str
    key_id: str
    ciphertext: str

    def decrypt(self, cipher: CredentialCipher) -> str:
        """Use the provided cipher to decrypt the envelope."""
        if cipher.algorithm != self.algorithm:
            msg = "Cipher algorithm mismatch during decryption."
            raise ValueError(msg)
        if cipher.key_id != self.key_id:
            msg = "Cipher key identifier mismatch during decryption."
            raise ValueError(msg)
        return cipher.decrypt(self)


class FernetCredentialCipher:
    """Credential cipher that leverages Fernet symmetric encryption."""

    algorithm: str = "fernet.v1"

    def __init__(self, *, key: str, key_id: str = "primary") -> None:
        """Derive a Fernet key from the provided secret string."""
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        derived_key = urlsafe_b64encode(digest)
        self._fernet = Fernet(derived_key)
        self.key_id = key_id

    def encrypt(self, plaintext: str) -> EncryptionEnvelope:
        """Encrypt plaintext credentials and return an envelope."""
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return EncryptionEnvelope(
            algorithm=self.algorithm,
            key_id=self.key_id,
            ciphertext=token.decode("utf-8"),
        )

    def decrypt(self, envelope: EncryptionEnvelope) -> str:
        """Decrypt an envelope previously produced by :meth:`encrypt`."""
        try:
            plaintext = self._fernet.decrypt(envelope.ciphertext.encode("utf-8"))
        except InvalidToken as exc:  # pragma: no cover - defensive
            msg = "Unable to decrypt credential payload with provided key."
            raise ValueError(msg) from exc
        return plaintext.decode("utf-8")


class CredentialMetadata(TimestampedAuditModel):
    """Metadata describing encrypted credentials associated with a workflow."""

    workflow_id: UUID
    name: str
    provider: str
    scopes: list[str] = Field(default_factory=list)
    encryption: EncryptionEnvelope
    last_rotated_at: datetime | None = None

    @field_validator("scopes", mode="after")
    @classmethod
    def _normalize_scopes(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for scope in value:
            candidate = scope.strip()
            if candidate and candidate not in seen:
                seen.add(candidate)
                normalized.append(candidate)
        return normalized

    @classmethod
    def create(
        cls,
        *,
        workflow_id: UUID,
        name: str,
        provider: str,
        scopes: Sequence[str],
        secret: str,
        cipher: CredentialCipher,
        actor: str,
    ) -> CredentialMetadata:
        """Construct a credential metadata record with encrypted secret."""
        encryption = cipher.encrypt(secret)
        metadata = cls(
            workflow_id=workflow_id,
            name=name,
            provider=provider,
            scopes=list(scopes),
            encryption=encryption,
        )
        metadata.record_event(actor=actor, action="credential_created")
        metadata.last_rotated_at = metadata.created_at
        return metadata

    def rotate_secret(
        self,
        *,
        secret: str,
        cipher: CredentialCipher,
        actor: str,
    ) -> None:
        """Rotate the secret value and update audit metadata."""
        self.encryption = cipher.encrypt(secret)
        now = _utcnow()
        self.last_rotated_at = now
        self.record_event(actor=actor, action="credential_rotated")

    def reveal(self, *, cipher: CredentialCipher) -> str:
        """Decrypt and return the credential secret."""
        return self.encryption.decrypt(cipher)

    def redact(self) -> MutableMapping[str, Any]:
        """Return a redacted representation suitable for logs."""
        return {
            "id": str(self.id),
            "workflow_id": str(self.workflow_id),
            "name": self.name,
            "provider": self.provider,
            "scopes": list(self.scopes),
            "last_rotated_at": self.last_rotated_at.isoformat()
            if self.last_rotated_at
            else None,
            "encryption": {
                "algorithm": self.encryption.algorithm,
                "key_id": self.encryption.key_id,
            },
        }
