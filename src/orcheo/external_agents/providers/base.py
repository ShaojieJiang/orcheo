"""Provider protocol and shared helpers for external agent adapters."""

from __future__ import annotations
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from orcheo.external_agents.models import AuthProbeResult, AuthStatus, ResolvedRuntime


SEMVER_PATTERN = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z_.-]+)?")


class ExternalAgentProvider(Protocol):
    """Provider contract used by the shared runtime manager."""

    name: str
    display_name: str
    package_name: str
    executable_name: str

    def install_command(self, install_prefix: Path) -> list[str]:
        """Return the latest-install command for ``install_prefix``."""

    def version_command(self, runtime: ResolvedRuntime) -> list[str]:
        """Return the version inspection command for ``runtime``."""

    def parse_version(self, result_stdout: str, result_stderr: str) -> str:
        """Extract a semantic version string from provider CLI output."""

    def probe_auth(
        self,
        runtime: ResolvedRuntime,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> AuthProbeResult:
        """Return a cheap readiness probe for provider authentication."""

    def build_command(
        self,
        runtime: ResolvedRuntime,
        *,
        prompt: str,
        system_prompt: str | None = None,
    ) -> list[str]:
        """Build the non-interactive provider invocation command."""

    def render_login_instructions(self, runtime: ResolvedRuntime) -> list[str]:
        """Return exact operator commands needed to authenticate the CLI."""

    def oauth_login_command(self, runtime: ResolvedRuntime) -> list[str]:
        """Return the interactive OAuth login command for the provider CLI."""

    def build_environment(
        self,
        environ: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Return the environment passed to install/auth/run commands."""


class NpmCliProvider:
    """Shared implementation for npm-distributed external agent CLIs."""

    name: str
    display_name: str
    package_name: str
    executable_name: str

    def install_command(self, install_prefix: Path) -> list[str]:
        """Install the latest provider CLI into ``install_prefix``."""
        return [
            "npm",
            "install",
            "--global",
            self.package_name,
            "--prefix",
            str(install_prefix),
        ]

    def version_command(self, runtime: ResolvedRuntime) -> list[str]:
        """Return the provider version command."""
        return [str(runtime.executable_path), "--version"]

    def parse_version(self, result_stdout: str, result_stderr: str) -> str:
        """Extract the first semantic version token from provider output."""
        combined = "\n".join(part for part in (result_stdout, result_stderr) if part)
        match = SEMVER_PATTERN.search(combined)
        if match is None:
            msg = f"Could not parse a runtime version from output: {combined!r}"
            raise ValueError(msg)
        return match.group(0)

    def executable_path(self, install_prefix: Path) -> Path:
        """Return the provider executable path inside ``install_prefix``."""
        return install_prefix / "bin" / self.executable_name

    def build_environment(
        self,
        environ: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Return the environment used for provider commands."""
        merged = dict(os.environ)
        if environ is not None:
            merged.update(environ)
        return merged

    def _authenticated_if_env_present(
        self,
        *,
        message: str,
        commands: list[str],
        environ: Mapping[str, str] | None,
        env_var_names: tuple[str, ...],
        auth_file: Path | None = None,
    ) -> AuthProbeResult:
        """Return a normalized auth probe from env vars and cached login files."""
        merged = self.build_environment(environ)
        if any(merged.get(name, "").strip() for name in env_var_names):
            return AuthProbeResult(status=AuthStatus.AUTHENTICATED)
        if auth_file is not None and auth_file.expanduser().exists():
            return AuthProbeResult(status=AuthStatus.AUTHENTICATED)
        return AuthProbeResult(
            status=AuthStatus.SETUP_NEEDED,
            message=message,
            commands=commands,
        )
