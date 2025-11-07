"""Repository specific error types."""

from __future__ import annotations


class RepositoryError(RuntimeError):
    """Base class for repository specific errors."""


class WorkflowNotFoundError(RepositoryError):
    """Raised when a workflow cannot be located."""


class WorkflowVersionNotFoundError(RepositoryError):
    """Raised when attempting to access an unknown workflow version."""


class WorkflowRunNotFoundError(RepositoryError):
    """Raised when attempting to access an unknown workflow run."""


__all__ = [
    "RepositoryError",
    "WorkflowNotFoundError",
    "WorkflowVersionNotFoundError",
    "WorkflowRunNotFoundError",
]
