"""Workflow-centric domain models with encryption and audit hooks."""

from __future__ import annotations
import hashlib
import json
import os
import re
from base64 import b64decode, b64encode, urlsafe_b64encode
from collections.abc import Mapping, MutableMapping, Sequence
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol
from uuid import UUID, uuid4
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
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


class AesGcmCredentialCipher:
    """Credential cipher backed by AES-256 GCM."""

    algorithm: str = "aes256-gcm.v1"

    def __init__(self, *, key: str, key_id: str = "primary") -> None:
        """Derive a 256-bit AES key from the provided secret."""
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        self._aesgcm = AESGCM(digest)
        self.key_id = key_id

    def encrypt(self, plaintext: str) -> EncryptionEnvelope:
        """Encrypt plaintext and return an envelope with nonce+ciphertext."""
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        payload = b64encode(nonce + ciphertext).decode("utf-8")
        return EncryptionEnvelope(
            algorithm=self.algorithm,
            key_id=self.key_id,
            ciphertext=payload,
        )

    def decrypt(self, envelope: EncryptionEnvelope) -> str:
        """Decrypt an :class:`EncryptionEnvelope` produced by this cipher."""
        try:
            decoded = b64decode(envelope.ciphertext.encode("utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            msg = "Encrypted payload is not valid base64 data."
            raise ValueError(msg) from exc

        if len(decoded) < 12:
            msg = "Encrypted payload is too short to contain a nonce."
            raise ValueError(msg)

        nonce = decoded[:12]
        ciphertext = decoded[12:]
        try:
            plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        except Exception as exc:  # pragma: no cover - defensive
            msg = "Unable to decrypt credential payload with provided key."
            raise ValueError(msg) from exc
        return plaintext.decode("utf-8")


class CredentialAccessContext(OrcheoBaseModel):
    """Describes the caller attempting to access a credential."""

    workflow_id: UUID | None = None
    workspace_id: UUID | None = None
    roles: list[str] = Field(default_factory=list)

    @field_validator("roles", mode="after")
    @classmethod
    def _normalize_roles(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for role in value:
            candidate = role.strip().lower()
            if candidate and candidate not in seen:
                seen.add(candidate)
                normalized.append(candidate)
        return normalized


class CredentialScope(OrcheoBaseModel):
    """Scope configuration declaring which callers may access a credential."""

    workflow_ids: list[UUID] = Field(default_factory=list)
    workspace_ids: list[UUID] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)

    @field_validator("workflow_ids", "workspace_ids", mode="after")
    @classmethod
    def _dedupe_uuid_list(cls, value: list[UUID]) -> list[UUID]:
        seen: set[UUID] = set()
        deduped: list[UUID] = []
        for item in value:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped

    @field_validator("roles", mode="after")
    @classmethod
    def _normalize_roles(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for role in value:
            candidate = role.strip().lower()
            if candidate and candidate not in seen:
                seen.add(candidate)
                normalized.append(candidate)
        return normalized

    @classmethod
    def unrestricted(cls) -> CredentialScope:
        """Return a scope that allows access from any context."""
        return cls()

    @classmethod
    def for_workflows(cls, *workflow_ids: UUID) -> CredentialScope:
        """Create a scope limited to the provided workflow identifiers."""
        return cls(workflow_ids=list(workflow_ids))

    @classmethod
    def for_workspaces(cls, *workspace_ids: UUID) -> CredentialScope:
        """Create a scope limited to the provided workspace identifiers."""
        return cls(workspace_ids=list(workspace_ids))

    @classmethod
    def for_roles(cls, *roles: str) -> CredentialScope:
        """Create a scope limited to callers possessing at least one role."""
        return cls(roles=[role for role in roles])

    def allows(self, context: CredentialAccessContext) -> bool:
        """Return whether the provided access context satisfies the scope."""
        if self.workflow_ids:
            if (
                context.workflow_id is None
                or context.workflow_id not in self.workflow_ids
            ):
                return False
        if self.workspace_ids:
            if (
                context.workspace_id is None
                or context.workspace_id not in self.workspace_ids
            ):
                return False
        if self.roles:
            if not context.roles:
                return False
            context_roles = set(context.roles)
            if not context_roles.intersection(self.roles):
                return False
        return True

    def is_unrestricted(self) -> bool:
        """Return whether the scope allows access from any context."""
        return not (self.workflow_ids or self.workspace_ids or self.roles)

    def scope_hint(self) -> str:
        """Return a stable string hint representing the most specific scope."""
        if self.workflow_ids:
            return str(self.workflow_ids[0])
        if self.workspace_ids:
            return str(self.workspace_ids[0])
        if self.roles:
            return self.roles[0]
        return "GLOBAL"


class CredentialKind(str, Enum):
    """Enumerates supported credential persistence strategies."""

    SECRET = "secret"
    OAUTH = "oauth"


class CredentialHealthStatus(str, Enum):
    """Represents the evaluated health state for a credential."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class OAuthTokenSecrets(OrcheoBaseModel):
    """Plaintext representation of OAuth tokens used by providers."""

    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _normalize_expiry(self) -> OAuthTokenSecrets:
        if self.expires_at and self.expires_at.tzinfo is None:
            object.__setattr__(self, "expires_at", self.expires_at.replace(tzinfo=UTC))
        return self


class OAuthTokenPayload(OrcheoBaseModel):
    """Encrypted storage for OAuth token secrets."""

    access_token: EncryptionEnvelope | None = None
    refresh_token: EncryptionEnvelope | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _normalize_expiry(self) -> OAuthTokenPayload:
        if self.expires_at and self.expires_at.tzinfo is None:
            object.__setattr__(self, "expires_at", self.expires_at.replace(tzinfo=UTC))
        return self

    @classmethod
    def from_secrets(
        cls, *, cipher: CredentialCipher, secrets: OAuthTokenSecrets | None
    ) -> OAuthTokenPayload:
        """Create an encrypted payload from plaintext OAuth tokens."""
        if secrets is None:
            return cls()
        return cls(
            access_token=cipher.encrypt(secrets.access_token)
            if secrets.access_token
            else None,
            refresh_token=cipher.encrypt(secrets.refresh_token)
            if secrets.refresh_token
            else None,
            expires_at=secrets.expires_at,
        )

    def reveal(self, *, cipher: CredentialCipher) -> OAuthTokenSecrets:
        """Return decrypted OAuth tokens from the encrypted payload."""
        return OAuthTokenSecrets(
            access_token=self.access_token.decrypt(cipher)
            if self.access_token
            else None,
            refresh_token=self.refresh_token.decrypt(cipher)
            if self.refresh_token
            else None,
            expires_at=self.expires_at,
        )

    def redact(self) -> MutableMapping[str, Any]:
        """Return redacted metadata describing stored OAuth tokens."""
        return {
            "has_access_token": self.access_token is not None,
            "has_refresh_token": self.refresh_token is not None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class CredentialHealth(OrcheoBaseModel):
    """Tracks the last known health evaluation for a credential."""

    status: CredentialHealthStatus = Field(default=CredentialHealthStatus.UNKNOWN)
    last_checked_at: datetime | None = None
    failure_reason: str | None = None

    def update(
        self, *, status: CredentialHealthStatus, reason: str | None = None
    ) -> None:
        """Update the health status and timestamp for the credential."""
        self.status = status
        self.last_checked_at = _utcnow()
        self.failure_reason = reason

    def redact(self) -> MutableMapping[str, Any]:
        """Return a redacted health payload for logging."""
        return {
            "status": self.status.value,
            "last_checked_at": self.last_checked_at.isoformat()
            if self.last_checked_at
            else None,
            "failure_reason": self.failure_reason,
        }


class CredentialMetadata(TimestampedAuditModel):
    """Metadata describing encrypted credentials with configurable scope."""

    name: str
    provider: str
    scopes: list[str] = Field(default_factory=list)
    scope: CredentialScope = Field(default_factory=CredentialScope.unrestricted)
    encryption: EncryptionEnvelope
    kind: CredentialKind = Field(default=CredentialKind.SECRET)
    oauth_tokens: OAuthTokenPayload | None = None
    health: CredentialHealth = Field(default_factory=CredentialHealth)
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
        name: str,
        provider: str,
        scopes: Sequence[str],
        secret: str,
        cipher: CredentialCipher,
        actor: str,
        scope: CredentialScope | None = None,
        kind: CredentialKind = CredentialKind.SECRET,
        oauth_tokens: OAuthTokenSecrets | None = None,
    ) -> CredentialMetadata:
        """Construct a credential metadata record with encrypted secret."""
        encryption = cipher.encrypt(secret)
        metadata = cls(
            name=name,
            provider=provider,
            scopes=list(scopes),
            scope=scope or CredentialScope.unrestricted(),
            encryption=encryption,
            kind=kind,
            oauth_tokens=OAuthTokenPayload.from_secrets(
                cipher=cipher, secrets=oauth_tokens
            )
            if kind is CredentialKind.OAUTH
            else None,
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
        if self.kind is CredentialKind.OAUTH:
            self.health.update(status=CredentialHealthStatus.UNKNOWN)

    def reveal(self, *, cipher: CredentialCipher) -> str:
        """Decrypt and return the credential secret."""
        return self.encryption.decrypt(cipher)

    def reveal_oauth_tokens(
        self, *, cipher: CredentialCipher
    ) -> OAuthTokenSecrets | None:
        """Return decrypted OAuth tokens when available."""
        if self.oauth_tokens is None:
            return None
        return self.oauth_tokens.reveal(cipher=cipher)

    def update_oauth_tokens(
        self,
        *,
        cipher: CredentialCipher,
        tokens: OAuthTokenSecrets | None,
        actor: str | None = None,
    ) -> None:
        """Persist updated OAuth tokens and reset cached health information."""
        if self.kind is not CredentialKind.OAUTH:
            msg = "OAuth tokens can only be updated for OAuth credentials."
            raise ValueError(msg)
        payload = OAuthTokenPayload.from_secrets(cipher=cipher, secrets=tokens)
        if (
            payload.access_token is None
            and payload.refresh_token is None
            and payload.expires_at is None
        ):
            self.oauth_tokens = None
        else:
            self.oauth_tokens = payload
        self.health.update(status=CredentialHealthStatus.UNKNOWN)
        self.record_event(
            actor=actor or "system",
            action="credential_oauth_tokens_updated",
        )

    def mark_health(
        self,
        *,
        status: CredentialHealthStatus,
        reason: str | None,
        actor: str | None = None,
    ) -> None:
        """Record the latest credential health evaluation for the metadata."""
        self.health.update(status=status, reason=reason)
        self.record_event(
            actor=actor or "system",
            action="credential_health_marked",
            metadata={
                "status": status.value,
                "reason": reason,
            },
        )

    def redact(self) -> MutableMapping[str, Any]:
        """Return a redacted representation suitable for logs."""
        return {
            "id": str(self.id),
            "name": self.name,
            "provider": self.provider,
            "scopes": list(self.scopes),
            "scope": self.scope.model_dump(),
            "kind": self.kind.value,
            "last_rotated_at": self.last_rotated_at.isoformat()
            if self.last_rotated_at
            else None,
            "encryption": {
                "algorithm": self.encryption.algorithm,
                "key_id": self.encryption.key_id,
            },
            "oauth_tokens": self.oauth_tokens.redact() if self.oauth_tokens else None,
            "health": self.health.redact(),
        }
