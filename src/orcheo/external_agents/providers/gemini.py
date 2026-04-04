"""Gemini CLI provider adapter."""

from __future__ import annotations
import json
from collections.abc import Mapping
from pathlib import Path
from orcheo.external_agents.models import AuthProbeResult, AuthStatus, ResolvedRuntime
from orcheo.external_agents.providers.base import NpmCliProvider


GEMINI_AUTH_JSON_ENV_VAR = "GEMINI_AUTH_JSON"
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

    def trusted_folders_path(
        self,
        environ: Mapping[str, str] | None = None,
    ) -> Path:
        """Return the Gemini trusted-folders cache path."""
        return self.gemini_home_path(environ) / "trustedFolders.json"

    def auth_artifact_paths(
        self,
        environ: Mapping[str, str] | None = None,
    ) -> tuple[Path, ...]:
        """Return Gemini auth artifacts stored under ``~/.gemini``."""
        gemini_home = self.gemini_home_path(environ)
        artifacts: list[Path] = []
        if gemini_home.exists():
            artifacts.extend(
                sorted(
                    path
                    for path in gemini_home.rglob("*")
                    if path.is_file()
                    and (path.suffix == ".json" or path.name == "installation_id")
                )
            )

        for required_path in (
            self.google_accounts_path(environ),
            self.state_path(environ),
            self.oauth_creds_path(environ),
            self.trusted_folders_path(environ),
        ):
            if required_path not in artifacts:
                artifacts.append(required_path)
        return tuple(artifacts)

    def serialize_auth_payload(
        self,
        environ: Mapping[str, str] | None = None,
    ) -> str | None:
        """Return a JSON payload bundling all Gemini auth artifacts."""
        gemini_home = self.gemini_home_path(environ)
        files_payload: dict[str, str] = {}
        for artifact_path in self.auth_artifact_paths(environ):
            if not artifact_path.exists():
                continue
            files_payload[str(artifact_path.relative_to(gemini_home))] = (
                artifact_path.read_text(encoding="utf-8")
            )
        if not files_payload:
            return None
        return json.dumps(
            {"version": 1, "files": files_payload},
            sort_keys=True,
            separators=(",", ":"),
        )

    def restore_auth_payload(
        self,
        payload: str,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        """Restore bundled Gemini auth artifacts into ``~/.gemini``."""
        loaded = json.loads(payload)
        if not isinstance(loaded, dict):
            msg = "GEMINI_AUTH_JSON must decode to a JSON object."
            raise ValueError(msg)
        if "files" in loaded:
            if loaded.get("version") != 1:
                msg = "GEMINI_AUTH_JSON version is unsupported."
                raise ValueError(msg)
            files_payload = loaded.get("files")
            if not isinstance(files_payload, dict):
                msg = "GEMINI_AUTH_JSON.files must decode to a JSON object."
                raise ValueError(msg)
        else:
            files_payload = loaded

        gemini_home = self.gemini_home_path(environ)
        gemini_home.mkdir(parents=True, exist_ok=True)
        for relative_name, file_contents in files_payload.items():
            relative_path = Path(str(relative_name))
            if relative_path.is_absolute() or ".." in relative_path.parts:
                msg = (
                    "GEMINI_AUTH_JSON contains an invalid artifact path "
                    f"{relative_name!r}."
                )
                raise ValueError(msg)
            if not isinstance(file_contents, str):
                msg = "GEMINI_AUTH_JSON must map artifact paths to string contents."
                raise ValueError(msg)
            target_path = gemini_home / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(file_contents, encoding="utf-8")
            target_path.chmod(0o600)

    def _auth_file_candidates(
        self,
        environ: Mapping[str, str] | None = None,
    ) -> tuple[Path, ...]:
        """Return Gemini auth files that indicate cached Google login."""
        return (self.oauth_creds_path(environ),)

    def probe_auth(
        self,
        runtime: ResolvedRuntime,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> AuthProbeResult:
        """Probe for env-based Gemini auth or cached Google-account login."""
        del runtime
        merged = self.build_environment(environ)
        if merged.get("GEMINI_API_KEY", "").strip():
            return AuthProbeResult(status=AuthStatus.AUTHENTICATED)
        if self.oauth_creds_path(merged).exists():
            return AuthProbeResult(status=AuthStatus.AUTHENTICATED)

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

        return AuthProbeResult(
            status=AuthStatus.SETUP_NEEDED,
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
        )

    def build_environment(
        self,
        environ: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Restore Gemini login artifacts before auth probes and runs."""
        merged = super().build_environment(environ)
        gemini_home = self.gemini_home_path(merged)
        gemini_home.mkdir(parents=True, exist_ok=True)

        bundled_payload = merged.get(GEMINI_AUTH_JSON_ENV_VAR, "").strip()
        if bundled_payload:
            self.restore_auth_payload(bundled_payload, merged)

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
