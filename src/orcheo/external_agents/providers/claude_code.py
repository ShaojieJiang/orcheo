"""Claude Code provider adapter."""

from __future__ import annotations
from collections.abc import Mapping
from pathlib import Path
from orcheo.external_agents.models import AuthProbeResult, ResolvedRuntime
from orcheo.external_agents.providers.base import NpmCliProvider


class ClaudeCodeProvider(NpmCliProvider):
    """Provider adapter for the published Claude Code CLI."""

    name = "claude_code"
    display_name = "Claude Code"
    package_name = "@anthropic-ai/claude-code"
    executable_name = "claude"

    def probe_auth(
        self,
        runtime: ResolvedRuntime,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> AuthProbeResult:
        """Probe for interactive Claude login or provider-native auth env vars."""
        del runtime
        return self._authenticated_if_env_present(
            message=(
                "Claude Code is installed but not authenticated on this worker. "
                "Complete the provider login flow on the worker host and rerun the "
                "workflow."
            ),
            commands=[
                f"{self.executable_name}",
                "export ANTHROPIC_API_KEY=<api-key>",
            ],
            environ=environ,
            env_var_names=(
                "ANTHROPIC_API_KEY",
                "CLAUDE_CODE_USE_BEDROCK",
                "CLAUDE_CODE_USE_VERTEX",
            ),
            auth_file=Path("~/.claude.json"),
        )

    def build_command(
        self,
        runtime: ResolvedRuntime,
        *,
        prompt: str,
        system_prompt: str | None = None,
    ) -> list[str]:
        """Build a non-interactive Claude Code invocation."""
        command = [
            str(runtime.executable_path),
            "--print",
            prompt,
            "--output-format",
            "text",
            "--permission-mode",
            "acceptEdits",
        ]
        if system_prompt:
            command.extend(["--append-system-prompt", system_prompt])
        return command

    def render_login_instructions(self, runtime: ResolvedRuntime) -> list[str]:
        """Render manual Claude Code login commands for setup-needed failures."""
        return [
            str(runtime.executable_path),
            "export ANTHROPIC_API_KEY=<api-key>",
        ]

    def oauth_login_command(self, runtime: ResolvedRuntime) -> list[str]:
        """Return the OAuth login command for Claude Code."""
        return [str(runtime.executable_path), "auth", "login"]
