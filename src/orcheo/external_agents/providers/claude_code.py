"""Claude Code provider adapter."""

from __future__ import annotations
import json
import subprocess
from collections.abc import Mapping
from orcheo.external_agents.models import AuthProbeResult, AuthStatus, ResolvedRuntime
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
        probe = self._authenticated_if_env_present(
            message="",
            commands=[],
            environ=environ,
            env_var_names=(
                "ANTHROPIC_API_KEY",
                "CLAUDE_CODE_OAUTH_TOKEN",
                "CLAUDE_CODE_USE_BEDROCK",
                "CLAUDE_CODE_USE_VERTEX",
            ),
        )
        if probe.authenticated:
            return probe

        message = (
            "Claude Code is installed but not authenticated on this worker. "
            "Complete the provider login flow on the worker host and rerun the "
            "workflow."
        )
        commands = [
            f"{self.executable_name} setup-token",
            "export CLAUDE_CODE_OAUTH_TOKEN=<oauth-token>",
            "export ANTHROPIC_API_KEY=<api-key>",
        ]

        try:
            result = subprocess.run(
                [str(runtime.executable_path), "auth", "status"],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
                env=self.build_environment(environ),
            )
        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            return AuthProbeResult(
                status=AuthStatus.SETUP_NEEDED,
                message=message,
                commands=commands,
            )

        if result.returncode == 0:
            try:
                payload = json.loads(result.stdout or "{}")
            except json.JSONDecodeError:
                payload = {}
            if payload.get("loggedIn") is True:
                return AuthProbeResult(status=AuthStatus.AUTHENTICATED)

        return AuthProbeResult(
            status=AuthStatus.SETUP_NEEDED,
            message=message,
            commands=commands,
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
            f"{runtime.executable_path} setup-token",
            "export CLAUDE_CODE_OAUTH_TOKEN=<oauth-token>",
            "export ANTHROPIC_API_KEY=<api-key>",
        ]

    def oauth_login_command(self, runtime: ResolvedRuntime) -> list[str]:
        """Return the OAuth login command for Claude Code."""
        return [str(runtime.executable_path), "setup-token"]
