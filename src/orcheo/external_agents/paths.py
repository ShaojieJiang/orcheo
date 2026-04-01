"""Filesystem helpers for managed external agent runtimes."""

from __future__ import annotations
import os
import subprocess
from pathlib import Path
from orcheo.external_agents.models import WorkingDirectoryValidationError


DEFAULT_RUNTIME_DIR_NAME = "agent-runtimes"
DEFAULT_RUNTIME_ROOT_UNDER_DATA = Path("/data") / DEFAULT_RUNTIME_DIR_NAME
DEFAULT_RUNTIME_ROOT_UNDER_HOME = Path("~/.orcheo") / DEFAULT_RUNTIME_DIR_NAME
RUNTIMES_DIR_NAME = "runtimes"
STAGING_DIR_NAME = "staging"


def default_runtime_root(
    *,
    data_root: Path = Path("/data"),
    home_directory: Path | None = None,
) -> Path:
    """Return the default managed runtime root for the current host."""
    if data_root.exists() and os.access(data_root, os.W_OK | os.X_OK):
        return data_root / DEFAULT_RUNTIME_DIR_NAME

    resolved_home = home_directory if home_directory is not None else Path.home()
    return resolved_home / ".orcheo" / DEFAULT_RUNTIME_DIR_NAME


def ensure_runtime_root(path: Path | None = None) -> Path:
    """Resolve and create the managed runtime root directory."""
    root = (path or default_runtime_root()).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def provider_root(runtime_root: Path, provider: str) -> Path:
    """Return the provider-local directory under ``runtime_root``."""
    return runtime_root / provider


def provider_manifest_path(runtime_root: Path, provider: str) -> Path:
    """Return the manifest path for ``provider``."""
    return provider_root(runtime_root, provider) / "manifest.json"


def provider_environment_path(runtime_root: Path, provider: str) -> Path:
    """Return the persisted provider environment path for ``provider``."""
    return provider_root(runtime_root, provider) / "environment.json"


def provider_lock_path(runtime_root: Path, provider: str) -> Path:
    """Return the advisory lock path for ``provider``."""
    return provider_root(runtime_root, provider) / ".lock"


def provider_runtimes_dir(runtime_root: Path, provider: str) -> Path:
    """Return the versioned runtimes directory for ``provider``."""
    return provider_root(runtime_root, provider) / RUNTIMES_DIR_NAME


def provider_staging_dir(runtime_root: Path, provider: str) -> Path:
    """Return the staging directory for ``provider`` installs."""
    return provider_root(runtime_root, provider) / STAGING_DIR_NAME


def validate_working_directory(
    candidate: str | Path,
    *,
    runtime_root: Path,
    home_directory: Path | None = None,
) -> Path:
    """Validate a requested working directory for external agent execution."""
    resolved = Path(candidate).expanduser().resolve(strict=True)
    runtime_root_resolved = runtime_root.expanduser().resolve()
    home_resolved = (
        home_directory.expanduser().resolve()
        if home_directory is not None
        else Path.home().resolve()
    )

    if not resolved.is_dir():
        msg = f"Working directory '{resolved}' is not a directory."
        raise WorkingDirectoryValidationError(msg)
    if resolved == Path(resolved.root):
        msg = "Refusing to run an external agent against '/'."
        raise WorkingDirectoryValidationError(msg)
    if resolved == home_resolved:
        msg = "Refusing to run an external agent against the worker home directory."
        raise WorkingDirectoryValidationError(msg)
    if resolved == runtime_root_resolved or resolved.is_relative_to(
        runtime_root_resolved
    ):
        msg = "Refusing to run an external agent inside the managed runtime root."
        raise WorkingDirectoryValidationError(msg)

    try:
        git_check = subprocess.run(
            ["git", "-C", str(resolved), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        msg = (
            "Git is required to validate external-agent working directories, but "
            "the 'git' executable is not available in this environment."
        )
        raise WorkingDirectoryValidationError(msg) from exc
    if git_check.returncode != 0:
        msg = (
            f"Working directory '{resolved}' must be a Git worktree root or a "
            "descendant inside a Git worktree."
        )
        raise WorkingDirectoryValidationError(msg)

    return resolved
