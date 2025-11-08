"""Workflow-centric entities and supporting utilities."""

from __future__ import annotations
import hashlib
import hmac
import json
import re
import secrets
from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Any, NotRequired, TypedDict
from uuid import UUID, uuid4
from pydantic import Field, field_validator, model_validator
from orcheo.models.base import TimestampedAuditModel, _utcnow


__all__ = [
    "Workflow",
    "WorkflowRun",
    "WorkflowRunStatus",
    "WorkflowVersion",
    "generate_publish_token",
    "hash_publish_token",
    "mask_publish_token",
]


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    """Convert the provided value into a workflow-safe slug."""
    normalized = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return normalized or value.strip().lower() or str(uuid4())


class WorkflowPublishMetadata(TypedDict):
    """Audit metadata for workflow publish events."""

    require_login: bool
    publish_token_hash: str


class WorkflowPublishTokenRotatedMetadata(TypedDict):
    """Audit metadata for publish token rotation events."""

    previous_token: str
    new_token: str


class WorkflowUnpublishedMetadata(TypedDict):
    """Audit metadata for workflow unpublish events."""

    previous_token: str
    require_login: bool


class WorkflowRunFailedMetadata(TypedDict):
    """Audit metadata captured when a workflow run fails."""

    error: str


class WorkflowRunCancelledMetadata(TypedDict, total=False):
    """Audit metadata captured when a workflow run is cancelled."""

    reason: NotRequired[str]


class Workflow(TimestampedAuditModel):
    """Represents a workflow container with metadata and audit trail."""

    name: str = Field(min_length=1, max_length=128)
    slug: str = ""
    description: str | None = Field(default=None, max_length=1024)
    tags: list[str] = Field(default_factory=list)
    is_archived: bool = False
    is_public: bool = False
    publish_token_hash: str | None = None
    published_at: datetime | None = None
    published_by: str | None = None
    publish_token_rotated_at: datetime | None = None
    require_login: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, value: object) -> str:
        candidate = str(value or "").strip()
        if not candidate:
            msg = "Workflow name must not be empty."
            raise ValueError(msg)
        return candidate

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: object) -> str | None:
        if value is None:
            return None
        candidate = str(value).strip()
        return candidate or None

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

    # -- Publish management -------------------------------------------------
    def publish(
        self,
        *,
        token_hash: str,
        require_login: bool,
        actor: str,
    ) -> None:
        """Mark the workflow as publicly accessible."""
        if not token_hash:
            msg = "Publish token hash must be provided."
            raise ValueError(msg)
        if self.is_public:
            msg = "Workflow is already published."
            raise ValueError(msg)

        now = _utcnow()
        metadata: WorkflowPublishMetadata = {
            "require_login": require_login,
            "publish_token_hash": token_hash,
        }
        self.is_public = True
        self.publish_token_hash = token_hash
        self.published_at = now
        self.published_by = actor
        self.publish_token_rotated_at = None
        self.require_login = require_login
        self.record_event(
            actor=actor,
            action="workflow_published",
            metadata=metadata,
        )

    def rotate_publish_token(
        self,
        *,
        token_hash: str,
        actor: str,
    ) -> None:
        """Rotate the publish token for an already published workflow."""
        if not token_hash:
            msg = "Publish token hash must be provided."
            raise ValueError(msg)
        if not self.is_public or not self.publish_token_hash:
            msg = "Workflow is not currently published."
            raise ValueError(msg)

        previous_hash = self.publish_token_hash
        metadata: WorkflowPublishTokenRotatedMetadata = {
            "previous_token": mask_publish_token(previous_hash),
            "new_token": mask_publish_token(token_hash),
        }
        self.publish_token_hash = token_hash
        self.publish_token_rotated_at = _utcnow()
        self.record_event(
            actor=actor,
            action="workflow_publish_token_rotated",
            metadata=metadata,
        )

    def revoke_publish(self, *, actor: str) -> None:
        """Revoke public access to the workflow."""
        if not self.is_public:
            msg = "Workflow is not currently published."
            raise ValueError(msg)

        metadata: WorkflowUnpublishedMetadata = {
            "previous_token": mask_publish_token(self.publish_token_hash or ""),
            "require_login": self.require_login,
        }
        self.is_public = False
        self.publish_token_hash = None
        self.published_at = None
        self.published_by = None
        self.publish_token_rotated_at = None
        self.require_login = False
        self.record_event(
            actor=actor,
            action="workflow_unpublished",
            metadata=metadata,
        )

    def verify_publish_token(self, token: str) -> bool:
        """Return True if ``token`` matches the stored publish token hash."""
        if not token or not self.publish_token_hash:
            return False
        candidate = hash_publish_token(token)
        return hmac.compare_digest(self.publish_token_hash, candidate)


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
        metadata: WorkflowRunFailedMetadata = {"error": error}
        self.record_event(actor=actor, action="run_failed", metadata=metadata)

    def mark_cancelled(self, *, actor: str, reason: str | None = None) -> None:
        """Cancel the run from a non-terminal state."""
        if self.status.is_terminal:
            msg = "Cannot cancel a run that is already completed."
            raise ValueError(msg)
        self.status = WorkflowRunStatus.CANCELLED
        self.completed_at = _utcnow()
        self.error = reason
        metadata: WorkflowRunCancelledMetadata = {}
        if reason:
            metadata["reason"] = reason
        self.record_event(actor=actor, action="run_cancelled", metadata=metadata)


_PUBLISH_TOKEN_BYTES = 32


def generate_publish_token(*, nbytes: int = _PUBLISH_TOKEN_BYTES) -> str:
    """Return a URL-safe publish token with at least 128 bits of entropy."""
    return secrets.token_urlsafe(max(16, nbytes))


def hash_publish_token(token: str) -> str:
    """Return the SHA-256 hash for the provided publish token."""
    digest = hashlib.sha256(token.encode("utf-8"))
    return digest.hexdigest()


def mask_publish_token(token_hash: str, *, reveal: int = 6) -> str:
    """Return a masked representation of a hashed publish token."""
    token_hash = token_hash or ""
    if not token_hash:
        return "publish:unknown"

    reveal = max(reveal, 0)
    suffix = token_hash[-reveal:] if reveal else ""
    masked_length = max(len(token_hash) - len(suffix), 3)
    masked_prefix = "*" * masked_length
    if suffix:
        return f"publish:{masked_prefix}{suffix}"
    return f"publish:{masked_prefix}"
