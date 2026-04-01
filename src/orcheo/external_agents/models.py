"""Shared models for external agent runtime management."""

from __future__ import annotations
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ExternalAgentError(RuntimeError):
    """Base exception for external agent runtime failures."""


class ProviderLockUnavailableError(ExternalAgentError):
    """Raised when a provider-local lock cannot be acquired immediately."""


class RuntimeVerificationError(ExternalAgentError):
    """Raised when a staged runtime cannot be verified."""


class RuntimeInstallError(ExternalAgentError):
    """Raised when a provider runtime install command fails."""

    def __init__(
        self,
        provider: str,
        message: str,
        *,
        command: list[str],
        stdout: str,
        stderr: str,
    ) -> None:
        """Initialize the install error with command output."""
        super().__init__(message)
        self.provider = provider
        self.command = command
        self.stdout = stdout
        self.stderr = stderr


class WorkingDirectoryValidationError(ExternalAgentError):
    """Raised when a requested working directory is unsafe or invalid."""


class AuthStatus(StrEnum):
    """Normalized authentication probe states."""

    AUTHENTICATED = "authenticated"
    SETUP_NEEDED = "setup_needed"
    ERROR = "error"


class ProcessExecutionResult(BaseModel):
    """Captured result for a managed subprocess invocation."""

    command: list[str]
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False
    duration_seconds: float


class AuthProbeResult(BaseModel):
    """Normalized result from a provider authentication probe."""

    status: AuthStatus
    message: str | None = None
    commands: list[str] = Field(default_factory=list)

    @property
    def authenticated(self) -> bool:
        """Return whether the provider is ready for execution."""
        return self.status == AuthStatus.AUTHENTICATED


class ResolvedRuntime(BaseModel):
    """Resolved immutable runtime selected for a node invocation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    provider: str
    version: str
    install_dir: Path
    executable_path: Path
    package_name: str
    installed_at: datetime | None = None

    @field_serializer("install_dir", "executable_path")
    def _serialize_path(self, value: Path) -> str:
        """Serialize filesystem paths as strings."""
        return str(value)


class RuntimeManifest(BaseModel):
    """Persisted provider manifest describing installed runtimes."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    provider: str
    provider_root: Path
    current_version: str | None = None
    current_runtime_path: Path | None = None
    previous_version: str | None = None
    previous_runtime_path: Path | None = None
    installed_at: datetime | None = None
    last_checked_at: datetime | None = None
    last_auth_ok_at: datetime | None = None

    @field_serializer("provider_root", "current_runtime_path", "previous_runtime_path")
    def _serialize_path(self, value: Path | None) -> str | None:
        """Serialize optional filesystem paths as strings."""
        if value is None:
            return None
        return str(value)


class RuntimeResolution(BaseModel):
    """Result returned when a provider runtime is resolved."""

    runtime: ResolvedRuntime
    maintenance_due: bool = False
    manifest: RuntimeManifest
