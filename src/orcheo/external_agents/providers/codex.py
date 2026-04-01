"""Codex provider adapter."""

from __future__ import annotations
from collections.abc import Mapping
from pathlib import Path
from orcheo.external_agents.models import AuthProbeResult, ResolvedRuntime
from orcheo.external_agents.providers.base import NpmCliProvider


class CodexProvider(NpmCliProvider):
    """Provider adapter for the published Codex CLI."""

    name = "codex"
    display_name = "Codex"
    package_name = "@openai/codex"
    executable_name = "codex"

    def probe_auth(
        self,
        runtime: ResolvedRuntime,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> AuthProbeResult:
        """Probe for saved Codex login or API-key auth."""
        del runtime
        return self._authenticated_if_env_present(
            message=(
                "Codex is installed but not authenticated on this worker. "
                "Sign in with ChatGPT or configure API-key auth, then rerun the "
                "workflow."
            ),
            commands=[
                f"{self.executable_name} login",
                "export CODEX_API_KEY=<api-key>",
            ],
            environ=environ,
            env_var_names=("CODEX_API_KEY", "OPENAI_API_KEY"),
            auth_file=Path("~/.codex/auth.json"),
        )

    def build_environment(
        self,
        environ: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Normalize OpenAI auth env vars for non-interactive Codex runs."""
        merged = super().build_environment(environ)
        if not merged.get("CODEX_API_KEY") and merged.get("OPENAI_API_KEY"):
            merged["CODEX_API_KEY"] = merged["OPENAI_API_KEY"]
        return merged

    def build_command(
        self,
        runtime: ResolvedRuntime,
        *,
        prompt: str,
        system_prompt: str | None = None,
    ) -> list[str]:
        """Build a non-interactive Codex CLI invocation."""
        combined_prompt = prompt
        if system_prompt:
            combined_prompt = (
                f"System instructions:\n{system_prompt.strip()}\n\nTask:\n{prompt}"
            )
        return [
            str(runtime.executable_path),
            "exec",
            "--skip-git-repo-check",
            "--full-auto",
            "--sandbox",
            "workspace-write",
            combined_prompt,
        ]

    def render_login_instructions(self, runtime: ResolvedRuntime) -> list[str]:
        """Render manual Codex login commands for setup-needed failures."""
        return [
            f"{runtime.executable_path} login",
            "export CODEX_API_KEY=<api-key>",
        ]

    def oauth_login_command(self, runtime: ResolvedRuntime) -> list[str]:
        """Return the device-auth login command for remote or containerized workers."""
        return [str(runtime.executable_path), "login", "--device-auth"]
