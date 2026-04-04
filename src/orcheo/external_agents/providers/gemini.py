"""Gemini CLI provider adapter."""

from __future__ import annotations
from collections.abc import Mapping
from pathlib import Path
from orcheo.external_agents.models import AuthProbeResult, AuthStatus, ResolvedRuntime
from orcheo.external_agents.providers.base import NpmCliProvider


GEMINI_GOOGLE_ACCOUNTS_JSON_ENV_VAR = "GEMINI_GOOGLE_ACCOUNTS_JSON"
GEMINI_STATE_JSON_ENV_VAR = "GEMINI_STATE_JSON"
GEMINI_OAUTH_CREDS_JSON_ENV_VAR = "GEMINI_OAUTH_CREDS_JSON"
GOOGLE_GENAI_USE_VERTEXAI_ENV_VAR = "GOOGLE_GENAI_USE_VERTEXAI"


class GeminiProvider(NpmCliProvider):
    """Provider adapter for the published Gemini CLI."""

    name = "gemini"
    display_name = "Gemini CLI"
    package_name = "@google/gemini-cli"
    executable_name = "gemini"

    def gemini_home_path(
        self,
        environ: Mapping[str, str] | None = None,
    ) -> Path:
        """Return the Gemini home directory for the provided environment."""
        merged = super().build_environment(environ)
        home = merged.get("HOME", "").strip()
        if home:
            return Path(home).expanduser() / ".gemini"
        return Path("~/.gemini").expanduser()

    def google_accounts_path(
        self,
        environ: Mapping[str, str] | None = None,
    ) -> Path:
        """Return the Google accounts cache path."""
        return self.gemini_home_path(environ) / "google_accounts.json"

    def state_path(
        self,
        environ: Mapping[str, str] | None = None,
    ) -> Path:
        """Return the Gemini state cache path."""
        return self.gemini_home_path(environ) / "state.json"

    def oauth_creds_path(
        self,
        environ: Mapping[str, str] | None = None,
    ) -> Path:
        """Return the OAuth credentials cache path."""
        return self.gemini_home_path(environ) / "oauth_creds.json"

    def _auth_file_candidates(
        self,
        environ: Mapping[str, str] | None = None,
    ) -> tuple[Path, ...]:
        """Return Gemini auth files that indicate cached Google login."""
        return (self.google_accounts_path(environ),)

    def probe_auth(
        self,
        runtime: ResolvedRuntime,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> AuthProbeResult:
        """Probe for env-based Gemini auth or cached Google-account login."""
        del runtime
        probe = self._authenticated_if_env_present(
            message=(
                "Gemini CLI is installed but not authenticated on this worker. "
                "Sign in with Google, configure GEMINI_API_KEY, or configure "
                "Vertex AI auth, then rerun the workflow."
            ),
            commands=[
                f"{self.executable_name} /auth signin",
                "export GEMINI_API_KEY=<api-key>",
                "export GOOGLE_GENAI_USE_VERTEXAI=true",
            ],
            environ=environ,
            env_var_names=(
                "GEMINI_API_KEY",
                GEMINI_GOOGLE_ACCOUNTS_JSON_ENV_VAR,
            ),
            auth_files=self._auth_file_candidates(environ),
        )
        if probe.authenticated:
            return probe

        merged = self.build_environment(environ)
        vertex_enabled = merged.get(
            GOOGLE_GENAI_USE_VERTEXAI_ENV_VAR, ""
        ).strip().lower() in {"1", "true", "yes", "on"}
        if (
            vertex_enabled
            and merged.get("GOOGLE_CLOUD_PROJECT", "").strip()
            and merged.get("GOOGLE_CLOUD_LOCATION", "").strip()
            and (
                merged.get("GOOGLE_API_KEY", "").strip()
                or merged.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
            )
        ):
            return AuthProbeResult(status=AuthStatus.AUTHENTICATED)

        return probe

    def build_environment(
        self,
        environ: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Restore Gemini login artifacts before auth probes and runs."""
        merged = super().build_environment(environ)
        gemini_home = self.gemini_home_path(merged)
        gemini_home.mkdir(parents=True, exist_ok=True)

        restore_targets = (
            (GEMINI_GOOGLE_ACCOUNTS_JSON_ENV_VAR, self.google_accounts_path(merged)),
            (GEMINI_STATE_JSON_ENV_VAR, self.state_path(merged)),
            (GEMINI_OAUTH_CREDS_JSON_ENV_VAR, self.oauth_creds_path(merged)),
        )
        for env_var_name, target_path in restore_targets:
            payload = merged.get(env_var_name, "").strip()
            if not payload:
                continue
            target_path.write_text(payload, encoding="utf-8")
            target_path.chmod(0o600)
        return merged

    def build_command(
        self,
        runtime: ResolvedRuntime,
        *,
        prompt: str,
        system_prompt: str | None = None,
    ) -> list[str]:
        """Build a non-interactive Gemini CLI invocation."""
        combined_prompt = prompt
        if system_prompt:
            combined_prompt = (
                f"System instructions:\n{system_prompt.strip()}\n\nTask:\n{prompt}"
            )
        return [
            str(runtime.executable_path),
            "--prompt",
            combined_prompt,
            "--approval-mode",
            "yolo",
            "--output-format",
            "text",
        ]

    def render_login_instructions(self, runtime: ResolvedRuntime) -> list[str]:
        """Render manual Gemini login commands for setup-needed failures."""
        return [
            f"{runtime.executable_path} /auth signin",
            "export GEMINI_API_KEY=<api-key>",
            "export GOOGLE_GENAI_USE_VERTEXAI=true",
        ]

    def oauth_login_command(self, runtime: ResolvedRuntime) -> list[str]:
        """Return the interactive Google login command for Gemini CLI."""
        return [str(runtime.executable_path), "/auth", "signin"]
