"""Tests for external agent runtime helpers and manager behavior."""

from __future__ import annotations
import multiprocessing
import subprocess
import sys
import time
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock
import pytest
from orcheo.external_agents.manifest import RuntimeManifestStore, provider_lock
from orcheo.external_agents.models import (
    AuthProbeResult,
    AuthStatus,
    ProcessExecutionResult,
    ProviderLockUnavailableError,
    ResolvedRuntime,
    RuntimeInstallError,
    RuntimeManifest,
    RuntimeVerificationError,
    WorkingDirectoryValidationError,
)
from orcheo.external_agents.paths import (
    default_runtime_root,
    provider_environment_path,
    validate_working_directory,
)
from orcheo.external_agents.providers.base import NpmCliProvider
from orcheo.external_agents.providers.claude_code import ClaudeCodeProvider
from orcheo.external_agents.providers.codex import CodexProvider
from orcheo.external_agents.runtime import (
    ExternalAgentRuntimeManager,
    scoped_external_agent_environment,
)


class FakeProvider(NpmCliProvider):
    """Provider implementation backed by a local helper executable."""

    name = "fake_agent"
    package_name = "@tests/fake-agent"
    executable_name = "fake-agent"

    def __init__(self, *, version: str = "1.0.0", authenticated: bool = True) -> None:
        """Initialize the fake provider."""
        self.version = version
        self.authenticated = authenticated
        self.fail_install = False

    def install_command(self, install_prefix: Path) -> list[str]:
        """Create a fake executable in ``install_prefix``."""
        script = f"""
from pathlib import Path
import sys

prefix = Path(sys.argv[1])
if sys.argv[2] == "1":
    raise SystemExit(9)
bin_dir = prefix / "bin"
bin_dir.mkdir(parents=True, exist_ok=True)
exe = bin_dir / "fake-agent"
exe.write_text(
    "#!/usr/bin/env python3\\n"
    "import sys\\n"
    "import time\\n"
    f"VERSION = {self.version!r}\\n"
    "args = sys.argv[1:]\\n"
    "if '--version' in args:\\n"
    "    print(f'fake-agent {{VERSION}}')\\n"
    "    raise SystemExit(0)\\n"
    "if any('timeout' in arg for arg in args):\\n"
    "    time.sleep(5)\\n"
    "if any('fail' in arg for arg in args):\\n"
    "    print('agent failed', file=sys.stderr)\\n"
    "    raise SystemExit(7)\\n"
    "print(' '.join(args))\\n",
    encoding='utf-8',
)
exe.chmod(0o755)
"""
        return [
            sys.executable,
            "-c",
            script,
            str(install_prefix),
            "1" if self.fail_install else "0",
        ]

    def probe_auth(
        self,
        runtime: ResolvedRuntime,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> AuthProbeResult:
        """Return a static auth response for tests."""
        del runtime, environ
        if self.authenticated:
            return AuthProbeResult(status=AuthStatus.AUTHENTICATED)
        return AuthProbeResult(
            status=AuthStatus.SETUP_NEEDED,
            message="Login required",
            commands=["fake-agent login"],
        )

    def build_command(
        self,
        runtime: ResolvedRuntime,
        *,
        prompt: str,
        system_prompt: str | None = None,
    ) -> list[str]:
        """Build a fake execution command."""
        combined_prompt = prompt
        if system_prompt:
            combined_prompt = f"{system_prompt} :: {prompt}"
        return [str(runtime.executable_path), combined_prompt]

    def render_login_instructions(self, runtime: ResolvedRuntime) -> list[str]:
        """Return fake login guidance."""
        del runtime
        return ["fake-agent login"]


def _hold_provider_lock(
    runtime_root: str,
    provider_name: str,
    ready: object,
) -> None:
    """Hold the provider lock briefly in a child process."""
    event = ready
    with provider_lock(Path(runtime_root), provider_name):
        event.set()
        time.sleep(1.5)


def test_default_runtime_root_prefers_writable_data_path(tmp_path: Path) -> None:
    """Writable /data-like roots are preferred over the home fallback."""
    data_root = tmp_path / "data"
    data_root.mkdir()

    resolved = default_runtime_root(
        data_root=data_root, home_directory=tmp_path / "home"
    )

    assert resolved == data_root / "agent-runtimes"


def test_default_runtime_root_falls_back_to_home(tmp_path: Path) -> None:
    """The home fallback is used when the data root does not exist."""
    home_directory = tmp_path / "home"

    resolved = default_runtime_root(
        data_root=tmp_path / "missing-data",
        home_directory=home_directory,
    )

    assert resolved == home_directory / ".orcheo" / "agent-runtimes"


def test_resolved_runtime_model_dump_serializes_paths(tmp_path: Path) -> None:
    runtime = ResolvedRuntime(
        provider="codex",
        version="1.2.3",
        install_dir=tmp_path / "runtime",
        executable_path=tmp_path / "runtime" / "bin" / "codex",
        package_name="@openai/codex",
    )

    payload = runtime.model_dump(mode="json")

    assert payload["install_dir"] == str(tmp_path / "runtime")
    assert payload["executable_path"] == str(tmp_path / "runtime" / "bin" / "codex")


def test_manifest_store_round_trip(tmp_path: Path) -> None:
    """Manifest store persists and reloads runtime metadata."""
    store = RuntimeManifestStore(tmp_path)
    manifest = RuntimeManifest(
        provider="codex",
        provider_root=tmp_path / "codex",
        current_version="1.2.3",
        current_runtime_path=tmp_path / "codex" / "runtimes" / "1.2.3",
        installed_at=datetime.now(UTC),
    )

    store.save(manifest)
    loaded = store.load("codex")

    assert loaded is not None
    assert loaded.current_version == "1.2.3"
    assert loaded.current_runtime_path == manifest.current_runtime_path


def test_provider_lock_blocks_parallel_access(tmp_path: Path) -> None:
    """Non-blocking provider lock acquisition fails while another process holds it."""
    ready = multiprocessing.Event()
    process = multiprocessing.Process(
        target=_hold_provider_lock,
        args=(str(tmp_path), "codex", ready),
    )
    process.start()
    assert ready.wait(timeout=5) is True

    with pytest.raises(ProviderLockUnavailableError):
        with provider_lock(tmp_path, "codex", blocking=False):
            pass

    process.join(timeout=5)
    assert process.exitcode == 0


def test_validate_working_directory_requires_git_and_rejects_runtime_root(
    tmp_path: Path,
) -> None:
    """Working-directory validation rejects unsafe targets and non-git paths."""
    runtime_root = tmp_path / "agent-runtimes"
    runtime_root.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "-C", str(repo), "init", "--quiet"],
        check=True,
    )

    validated = validate_working_directory(repo, runtime_root=runtime_root)
    assert validated == repo.resolve()

    with pytest.raises(WorkingDirectoryValidationError):
        validate_working_directory(runtime_root, runtime_root=runtime_root)

    plain_dir = tmp_path / "plain"
    plain_dir.mkdir()
    with pytest.raises(WorkingDirectoryValidationError):
        validate_working_directory(plain_dir, runtime_root=runtime_root)


def test_validate_working_directory_surfaces_missing_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing git returns a validation error instead of crashing the backend."""
    runtime_root = tmp_path / "agent-runtimes"
    runtime_root.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()

    def _raise_missing_git(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(2, "No such file or directory", "git")

    monkeypatch.setattr(subprocess, "run", _raise_missing_git)

    with pytest.raises(WorkingDirectoryValidationError, match="Git is required"):
        validate_working_directory(repo, runtime_root=runtime_root)


def test_validate_working_directory_rejects_non_directory(tmp_path: Path) -> None:
    runtime_root = tmp_path / "agent-runtimes"
    runtime_root.mkdir()
    file_path = tmp_path / "not-a-dir.txt"
    file_path.write_text("x", encoding="utf-8")

    with pytest.raises(WorkingDirectoryValidationError, match="is not a directory"):
        validate_working_directory(file_path, runtime_root=runtime_root)


def test_validate_working_directory_rejects_root_directory(tmp_path: Path) -> None:
    runtime_root = tmp_path / "agent-runtimes"
    runtime_root.mkdir()

    with pytest.raises(WorkingDirectoryValidationError, match="against '/'"):
        validate_working_directory("/", runtime_root=runtime_root)


def test_validate_working_directory_rejects_home_directory(tmp_path: Path) -> None:
    runtime_root = tmp_path / "agent-runtimes"
    runtime_root.mkdir()
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    subprocess.run(["git", "-C", str(home_directory), "init", "--quiet"], check=True)

    with pytest.raises(WorkingDirectoryValidationError, match="worker home directory"):
        validate_working_directory(
            home_directory,
            runtime_root=runtime_root,
            home_directory=home_directory,
        )


def test_maintenance_due_uses_last_check_and_install_time(tmp_path: Path) -> None:
    """Maintenance due is driven by last_checked_at, falling back to installed_at."""
    manager = ExternalAgentRuntimeManager(runtime_root=tmp_path)
    now = datetime.now(UTC)
    old_manifest = RuntimeManifest(
        provider="codex",
        provider_root=tmp_path / "codex",
        installed_at=now - timedelta(days=10),
    )
    fresh_manifest = RuntimeManifest(
        provider="codex",
        provider_root=tmp_path / "codex",
        installed_at=now - timedelta(days=1),
    )
    checked_manifest = RuntimeManifest(
        provider="codex",
        provider_root=tmp_path / "codex",
        installed_at=now - timedelta(days=30),
        last_checked_at=now - timedelta(days=2),
    )

    assert manager.maintenance_due(old_manifest, now=now) is True
    assert manager.maintenance_due(fresh_manifest, now=now) is False
    assert manager.maintenance_due(checked_manifest, now=now) is False


def test_maintenance_due_returns_true_when_manifest_missing(tmp_path: Path) -> None:
    manager = ExternalAgentRuntimeManager(runtime_root=tmp_path)
    assert manager.maintenance_due(None) is True


@pytest.mark.asyncio
async def test_runtime_manager_installs_and_reuses_runtime(tmp_path: Path) -> None:
    """First resolution installs a runtime and later resolutions reuse it."""
    provider = FakeProvider(version="1.0.0")
    manager = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        providers={provider.name: provider},
    )

    first = await manager.resolve_runtime(provider.name)
    second = await manager.resolve_runtime(provider.name)

    assert first.runtime.version == "1.0.0"
    assert first.runtime.executable_path.exists()
    assert second.runtime.install_dir == first.runtime.install_dir
    assert second.maintenance_due is False


@pytest.mark.asyncio
async def test_runtime_manager_successful_maintenance_keeps_previous_version(
    tmp_path: Path,
) -> None:
    """Maintenance upgrades stage side-by-side and retain one previous runtime."""
    provider = FakeProvider(version="1.0.0")
    manager = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        providers={provider.name: provider},
    )
    await manager.resolve_runtime(provider.name)
    manifest = manager.manifest_store.load(provider.name)
    assert manifest is not None
    manifest.installed_at = datetime.now(UTC) - timedelta(days=10)
    manager.manifest_store.save(manifest)

    provider.version = "2.0.0"
    result = await manager.run_maintenance(provider.name)

    assert result.runtime.version == "2.0.0"
    assert result.manifest.previous_version == "1.0.0"
    previous_path = result.manifest.previous_runtime_path
    assert previous_path is not None and previous_path.exists()


@pytest.mark.asyncio
async def test_runtime_manager_failed_maintenance_keeps_current_runtime(
    tmp_path: Path,
) -> None:
    """Failed maintenance leaves the last known-good runtime active."""
    provider = FakeProvider(version="1.0.0")
    manager = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        providers={provider.name: provider},
    )
    first = await manager.resolve_runtime(provider.name)
    manifest = manager.manifest_store.load(provider.name)
    assert manifest is not None
    manifest.installed_at = datetime.now(UTC) - timedelta(days=10)
    manager.manifest_store.save(manifest)
    provider.version = "2.0.0"
    provider.fail_install = True

    with pytest.raises(RuntimeInstallError):
        await manager.run_maintenance(provider.name)

    manifest = manager.manifest_store.load(provider.name)
    assert manifest is not None
    assert manifest.current_version == "1.0.0"
    assert first.runtime.install_dir.exists()


def test_codex_provider_builds_expected_command() -> None:
    """Codex provider builds a non-interactive full-auto invocation."""
    provider = CodexProvider()
    runtime = ResolvedRuntime(
        provider="codex",
        version="0.0.1",
        install_dir=Path("/tmp/codex"),
        executable_path=Path("/tmp/codex/bin/codex"),
        package_name=provider.package_name,
    )

    command = provider.build_command(
        runtime,
        prompt="fix tests",
        system_prompt="be minimal",
    )

    assert command[:6] == [
        "/tmp/codex/bin/codex",
        "exec",
        "--skip-git-repo-check",
        "--full-auto",
        "--sandbox",
        "workspace-write",
    ]
    assert "System instructions:" in command[-1]


def test_codex_provider_builds_expected_command_without_system_prompt() -> None:
    provider = CodexProvider()
    runtime = ResolvedRuntime(
        provider="codex",
        version="0.0.1",
        install_dir=Path("/tmp/codex"),
        executable_path=Path("/tmp/codex/bin/codex"),
        package_name=provider.package_name,
    )

    command = provider.build_command(runtime, prompt="fix tests")

    assert command[-1] == "fix tests"


def test_codex_provider_renders_login_instructions() -> None:
    provider = CodexProvider()
    runtime = ResolvedRuntime(
        provider="codex",
        version="0.0.1",
        install_dir=Path("/tmp/codex"),
        executable_path=Path("/tmp/codex/bin/codex"),
        package_name=provider.package_name,
    )

    assert provider.render_login_instructions(runtime) == [
        "/tmp/codex/bin/codex login",
        "export CODEX_API_KEY=<api-key>",
    ]


def test_codex_provider_uses_device_auth_login() -> None:
    """Codex provider should use device auth for remote worker login flows."""
    provider = CodexProvider()
    runtime = ResolvedRuntime(
        provider="codex",
        version="0.0.1",
        install_dir=Path("/tmp/codex"),
        executable_path=Path("/tmp/codex/bin/codex"),
        package_name=provider.package_name,
    )

    assert provider.oauth_login_command(runtime) == [
        "/tmp/codex/bin/codex",
        "login",
        "--device-auth",
    ]


def test_codex_provider_build_environment_creates_codex_home(
    tmp_path: Path,
) -> None:
    """Configured CODEX_HOME should exist before invoking the Codex CLI."""
    provider = CodexProvider()
    codex_home = tmp_path / "codex-home"

    environ = provider.build_environment(
        {
            "CODEX_HOME": str(codex_home),
            "OPENAI_API_KEY": "test-openai-key",
        }
    )

    assert codex_home.is_dir()
    assert environ["CODEX_API_KEY"] == "test-openai-key"


def test_codex_provider_build_environment_restores_auth_json(
    tmp_path: Path,
) -> None:
    """Vault-sourced auth.json should be restored before Codex auth probes."""
    provider = CodexProvider()
    codex_home = tmp_path / "codex-home"

    provider.build_environment(
        {
            "CODEX_HOME": str(codex_home),
            "CODEX_AUTH_JSON": '{"auth_mode":"chatgpt"}',
        }
    )

    assert (codex_home / "auth.json").read_text(encoding="utf-8") == (
        '{"auth_mode":"chatgpt"}'
    )


def test_claude_provider_uses_setup_token_login() -> None:
    """Claude provider should use setup-token for worker login flows."""
    provider = ClaudeCodeProvider()
    runtime = ResolvedRuntime(
        provider="claude_code",
        version="0.0.1",
        install_dir=Path("/tmp/claude"),
        executable_path=Path("/tmp/claude/bin/claude"),
        package_name=provider.package_name,
    )

    assert provider.oauth_login_command(runtime) == [
        "/tmp/claude/bin/claude",
        "setup-token",
    ]


def test_claude_provider_builds_expected_command() -> None:
    """Claude provider uses print mode with appended system instructions."""
    provider = ClaudeCodeProvider()
    runtime = ResolvedRuntime(
        provider="claude_code",
        version="0.0.1",
        install_dir=Path("/tmp/claude"),
        executable_path=Path("/tmp/claude/bin/claude"),
        package_name=provider.package_name,
    )

    command = provider.build_command(
        runtime,
        prompt="review",
        system_prompt="be concise",
    )

    assert command[:6] == [
        "/tmp/claude/bin/claude",
        "--print",
        "review",
        "--output-format",
        "text",
        "--permission-mode",
    ]
    assert "--append-system-prompt" in command


def test_claude_provider_builds_expected_command_without_system_prompt() -> None:
    provider = ClaudeCodeProvider()
    runtime = ResolvedRuntime(
        provider="claude_code",
        version="0.0.1",
        install_dir=Path("/tmp/claude"),
        executable_path=Path("/tmp/claude/bin/claude"),
        package_name=provider.package_name,
    )

    command = provider.build_command(runtime, prompt="review")

    assert "--append-system-prompt" not in command


def test_claude_provider_renders_login_instructions() -> None:
    provider = ClaudeCodeProvider()
    runtime = ResolvedRuntime(
        provider="claude_code",
        version="0.0.1",
        install_dir=Path("/tmp/claude"),
        executable_path=Path("/tmp/claude/bin/claude"),
        package_name=provider.package_name,
    )

    assert provider.render_login_instructions(runtime) == [
        "/tmp/claude/bin/claude setup-token",
        "export CLAUDE_CODE_OAUTH_TOKEN=<oauth-token>",
        "export ANTHROPIC_API_KEY=<api-key>",
    ]


def test_provider_version_parsing_and_auth_probes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Providers parse versions and detect saved auth or env-based auth."""
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    codex = CodexProvider()
    claude = ClaudeCodeProvider()
    runtime = ResolvedRuntime(
        provider="codex",
        version="0.0.1",
        install_dir=tmp_path,
        executable_path=tmp_path / "bin" / "fake",
        package_name="pkg",
    )

    assert codex.parse_version("codex 1.2.3", "") == "1.2.3"
    assert claude.parse_version("", "claude 4.5.0") == "4.5.0"

    missing_codex = codex.probe_auth(runtime, environ={})
    assert missing_codex.status == AuthStatus.SETUP_NEEDED

    env_auth_json_codex = codex.probe_auth(
        runtime,
        environ={"CODEX_AUTH_JSON": '{"auth_mode":"chatgpt"}'},
    )
    assert env_auth_json_codex.status == AuthStatus.AUTHENTICATED

    auth_dir = tmp_path / ".codex"
    auth_dir.mkdir(exist_ok=True)
    (auth_dir / "auth.json").write_text("{}", encoding="utf-8")
    cached_codex = codex.probe_auth(runtime, environ={})
    assert cached_codex.status == AuthStatus.AUTHENTICATED

    custom_codex_home = tmp_path / "codex-home"
    custom_codex_home.mkdir()
    (custom_codex_home / "auth.json").write_text("{}", encoding="utf-8")
    codex_with_explicit_home = codex.probe_auth(
        runtime,
        environ={"CODEX_HOME": str(custom_codex_home)},
    )
    assert codex_with_explicit_home.status == AuthStatus.AUTHENTICATED

    status_not_logged_in = Mock(
        return_value=subprocess.CompletedProcess(
            args=["claude", "auth", "status"],
            returncode=0,
            stdout='{"loggedIn": false, "authMethod": "none"}',
            stderr="",
        )
    )
    monkeypatch.setattr(subprocess, "run", status_not_logged_in)
    stale_claude_metadata = tmp_path / ".claude.json"
    stale_claude_metadata.write_text("{}", encoding="utf-8")
    cached_claude = claude.probe_auth(runtime, environ={})
    assert cached_claude.status == AuthStatus.SETUP_NEEDED

    env_claude = claude.probe_auth(runtime, environ={"ANTHROPIC_API_KEY": "x"})
    assert env_claude.status == AuthStatus.AUTHENTICATED

    oauth_token_claude = claude.probe_auth(
        runtime,
        environ={"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-test"},
    )
    assert oauth_token_claude.status == AuthStatus.AUTHENTICATED

    status_logged_in = Mock(
        return_value=subprocess.CompletedProcess(
            args=["claude", "auth", "status"],
            returncode=0,
            stdout='{"loggedIn": true, "authMethod": "oauth"}',
            stderr="",
        )
    )
    monkeypatch.setattr(subprocess, "run", status_logged_in)
    oauth_claude = claude.probe_auth(runtime, environ={})
    assert oauth_claude.status == AuthStatus.AUTHENTICATED


def test_claude_probe_auth_handles_subprocess_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ClaudeCodeProvider()
    runtime = ResolvedRuntime(
        provider="claude_code",
        version="0.0.1",
        install_dir=tmp_path,
        executable_path=tmp_path / "bin" / "claude",
        package_name=provider.package_name,
    )

    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(side_effect=OSError("boom")),
    )

    result = provider.probe_auth(runtime, environ={})
    assert result.status == AuthStatus.SETUP_NEEDED


def test_claude_probe_auth_handles_invalid_json_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ClaudeCodeProvider()
    runtime = ResolvedRuntime(
        provider="claude_code",
        version="0.0.1",
        install_dir=tmp_path,
        executable_path=tmp_path / "bin" / "claude",
        package_name=provider.package_name,
    )

    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(
            return_value=subprocess.CompletedProcess(
                args=["claude", "auth", "status"],
                returncode=0,
                stdout="{invalid-json",
                stderr="",
            )
        ),
    )

    result = provider.probe_auth(runtime, environ={})
    assert result.status == AuthStatus.SETUP_NEEDED


def test_claude_probe_auth_handles_nonzero_status_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ClaudeCodeProvider()
    runtime = ResolvedRuntime(
        provider="claude_code",
        version="0.0.1",
        install_dir=tmp_path,
        executable_path=tmp_path / "bin" / "claude",
        package_name=provider.package_name,
    )

    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(
            return_value=subprocess.CompletedProcess(
                args=["claude", "auth", "status"],
                returncode=1,
                stdout="",
                stderr="not logged in",
            )
        ),
    )

    result = provider.probe_auth(runtime, environ={})
    assert result.status == AuthStatus.SETUP_NEEDED


def test_runtime_manager_persists_provider_environment(tmp_path: Path) -> None:
    """Provider-specific environment variables should persist across managers."""
    manager = ExternalAgentRuntimeManager(runtime_root=tmp_path, environ={})

    manager.save_provider_environment(
        "claude_code",
        {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-test-token"},
    )

    first = manager.environment_for_provider("claude_code")
    second = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        environ={},
    ).environment_for_provider("claude_code")

    assert first["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-test-token"
    assert second["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-test-token"


def test_runtime_manager_respects_scoped_environment_overrides(tmp_path: Path) -> None:
    """Scoped environment overrides should influence managers created within the context."""  # noqa: E501
    with scoped_external_agent_environment({"SCOPED_VAR": "scoped-value"}):
        scoped_manager = ExternalAgentRuntimeManager(runtime_root=tmp_path, environ={})
        assert scoped_manager.environ["SCOPED_VAR"] == "scoped-value"

    non_scoped_manager = ExternalAgentRuntimeManager(runtime_root=tmp_path, environ={})
    assert "SCOPED_VAR" not in non_scoped_manager.environ


def test_get_provider_unknown_raises(tmp_path: Path) -> None:
    manager = ExternalAgentRuntimeManager(runtime_root=tmp_path, providers={})
    with pytest.raises(ValueError, match="Unknown external agent provider"):
        manager.get_provider("missing")


def test_validate_working_directory_delegates_to_paths_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = ExternalAgentRuntimeManager(runtime_root=tmp_path)
    expected = tmp_path / "repo"
    monkeypatch.setattr(
        "orcheo.external_agents.runtime.validate_working_directory",
        lambda candidate, *, runtime_root: expected,
    )

    assert manager.validate_working_directory("repo") == expected


def test_save_provider_environment_removes_empty_values(tmp_path: Path) -> None:
    manager = ExternalAgentRuntimeManager(runtime_root=tmp_path, environ={})
    manager.save_provider_environment("claude_code", {"FOO": "bar"})
    updated = manager.save_provider_environment("claude_code", {"FOO": " ", "BAR": "1"})

    assert "FOO" not in updated
    assert manager.environ["BAR"] == "1"


def test_maintenance_due_without_timestamps_is_true(tmp_path: Path) -> None:
    manager = ExternalAgentRuntimeManager(runtime_root=tmp_path)
    manifest = RuntimeManifest(provider="codex", provider_root=tmp_path / "codex")
    assert manager.maintenance_due(manifest) is True


def test_mark_auth_success_updates_manifest_timestamp(tmp_path: Path) -> None:
    manager = ExternalAgentRuntimeManager(runtime_root=tmp_path)
    manifest = RuntimeManifest(provider="codex", provider_root=tmp_path / "codex")
    manager.manifest_store.save(manifest)

    updated = manager.mark_auth_success("codex")

    assert updated.last_auth_ok_at is not None


def test_inspect_runtime_returns_runtime_when_executable_exists(
    tmp_path: Path,
) -> None:
    provider = FakeProvider()
    manager = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        providers={provider.name: provider},
    )
    runtime_dir = tmp_path / provider.name / "runtimes" / "1.0.0"
    bin_dir = runtime_dir / "bin"
    bin_dir.mkdir(parents=True)
    executable = bin_dir / provider.executable_name
    executable.write_text("", encoding="utf-8")
    manifest = RuntimeManifest(
        provider=provider.name,
        provider_root=tmp_path / provider.name,
        current_version="1.0.0",
        current_runtime_path=runtime_dir,
    )
    manager.manifest_store.save(manifest)

    resolved, _ = manager.inspect_runtime(provider.name)
    assert resolved is not None
    assert resolved.version == "1.0.0"


@pytest.mark.asyncio
async def test_run_maintenance_installs_when_manifest_missing(
    tmp_path: Path,
) -> None:
    provider = FakeProvider()
    manager = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        providers={provider.name: provider},
    )
    runtime = ResolvedRuntime(
        provider=provider.name,
        version="2.0.0",
        install_dir=tmp_path / "runtimes" / "2.0.0",
        executable_path=tmp_path
        / "runtimes"
        / "2.0.0"
        / "bin"
        / provider.executable_name,
        package_name=provider.package_name,
    )
    manifest = RuntimeManifest(
        provider=provider.name,
        provider_root=tmp_path / provider.name,
        current_version="2.0.0",
        current_runtime_path=runtime.install_dir,
    )

    async def fake_install(self, _provider, _manifest):
        return runtime, manifest

    manager._install_latest_locked = fake_install.__get__(
        manager, ExternalAgentRuntimeManager
    )

    result = await manager.run_maintenance(provider.name)

    assert result.runtime.version == "2.0.0"
    assert result.manifest.current_version == "2.0.0"
    assert result.maintenance_due is False


@pytest.mark.asyncio
async def test_run_maintenance_installs_when_current_runtime_missing(
    tmp_path: Path,
) -> None:
    provider = FakeProvider()
    manager = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        providers={provider.name: provider},
    )
    missing_runtime = tmp_path / provider.name / "runtimes" / "missing"
    manifest = RuntimeManifest(
        provider=provider.name,
        provider_root=tmp_path / provider.name,
        current_version="1.0.0",
        current_runtime_path=missing_runtime,
    )
    manager.manifest_store.save(manifest)
    runtime = ResolvedRuntime(
        provider=provider.name,
        version="3.0.0",
        install_dir=tmp_path / provider.name / "runtimes" / "3.0.0",
        executable_path=tmp_path
        / provider.name
        / "runtimes"
        / "3.0.0"
        / "bin"
        / provider.executable_name,
        package_name=provider.package_name,
    )

    async def fake_install(self, _provider, _manifest):
        return runtime, RuntimeManifest(
            provider=provider.name,
            provider_root=tmp_path / provider.name,
            current_version="3.0.0",
            current_runtime_path=runtime.install_dir,
        )

    manager._install_latest_locked = fake_install.__get__(
        manager, ExternalAgentRuntimeManager
    )

    result = await manager.run_maintenance(provider.name)
    assert result.runtime.version == "3.0.0"
    assert result.maintenance_due is False


@pytest.mark.asyncio
async def test_run_maintenance_returns_current_runtime_when_not_due(
    tmp_path: Path,
) -> None:
    provider = FakeProvider()
    manager = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        providers={provider.name: provider},
    )
    now = datetime.now(UTC)
    runtime_dir = tmp_path / provider.name / "runtimes" / "fresh"
    bin_dir = runtime_dir / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / provider.executable_name).write_text("", encoding="utf-8")
    manifest = RuntimeManifest(
        provider=provider.name,
        provider_root=tmp_path / provider.name,
        current_version="1.1.1",
        current_runtime_path=runtime_dir,
        installed_at=now - timedelta(days=1),
        last_checked_at=now,
    )
    manager.manifest_store.save(manifest)

    async def _fail_install(
        *args: object, **kwargs: object
    ) -> tuple[ResolvedRuntime, RuntimeManifest]:
        raise AssertionError("install should not be called")

    manager._install_latest_locked = _fail_install  # type: ignore[assignment]

    result = await manager.run_maintenance(provider.name)
    assert result.runtime.version == "1.1.1"
    assert result.manifest.current_version == "1.1.1"
    assert result.maintenance_due is False


def test_mark_auth_success_requires_manifest(tmp_path: Path) -> None:
    manager = ExternalAgentRuntimeManager(runtime_root=tmp_path)
    with pytest.raises(ValueError, match="Cannot record auth success"):
        manager.mark_auth_success("unknown")


@pytest.mark.asyncio
async def test_install_latest_locked_raises_on_install_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = StubInstallProvider()
    manager = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        providers={provider.name: provider},
    )

    async def fake_install(
        command: list[str], **kwargs: object
    ) -> ProcessExecutionResult:
        return ProcessExecutionResult(
            command=command,
            exit_code=1,
            stdout="",
            stderr="",
            duration_seconds=0,
        )

    monkeypatch.setattr(
        "orcheo.external_agents.runtime.execute_process",
        fake_install,
    )

    with pytest.raises(RuntimeInstallError):
        await manager._install_latest_locked(provider, None)


@pytest.mark.asyncio
async def test_install_latest_locked_raises_when_executable_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = StubInstallProvider()
    manager = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        providers={provider.name: provider},
    )

    async def fake_execute(
        command: list[str], **kwargs: object
    ) -> ProcessExecutionResult:
        if command[0] == "stub-install":
            return ProcessExecutionResult(
                command=command,
                exit_code=0,
                stdout="",
                stderr="",
                duration_seconds=0,
            )
        return ProcessExecutionResult(
            command=command,
            exit_code=0,
            stdout="1.2.3",
            stderr="",
            duration_seconds=0,
        )

    monkeypatch.setattr(
        "orcheo.external_agents.runtime.execute_process",
        fake_execute,
    )

    with pytest.raises(RuntimeVerificationError):
        await manager._install_latest_locked(provider, None)


@pytest.mark.asyncio
async def test_install_latest_locked_raises_when_version_check_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = StubInstallProvider()
    manager = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        providers={provider.name: provider},
    )

    async def fake_execute(
        command: list[str], **kwargs: object
    ) -> ProcessExecutionResult:
        if command[0] == "stub-install":
            staged_dir = Path(command[-1])
            (staged_dir / "bin").mkdir(parents=True, exist_ok=True)
            (staged_dir / "bin" / provider.executable_name).write_text(
                "", encoding="utf-8"
            )
            return ProcessExecutionResult(
                command=command,
                exit_code=0,
                stdout="",
                stderr="",
                duration_seconds=0,
            )
        return ProcessExecutionResult(
            command=command,
            exit_code=1,
            stdout="",
            stderr="failure",
            duration_seconds=0,
        )

    monkeypatch.setattr(
        "orcheo.external_agents.runtime.execute_process",
        fake_execute,
    )

    with pytest.raises(RuntimeVerificationError):
        await manager._install_latest_locked(provider, None)


@pytest.mark.asyncio
async def test_install_latest_locked_retains_previous_on_same_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = StubInstallProvider()
    manager = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        providers={provider.name: provider},
    )
    base_manifest = RuntimeManifest(
        provider=provider.name,
        provider_root=tmp_path / provider.name,
        current_version="1.0.0",
        current_runtime_path=tmp_path / provider.name / "runtimes" / "1.0.0",
        previous_version="0.9.0",
        previous_runtime_path=tmp_path / provider.name / "runtimes" / "0.9.0",
    )

    async def fake_execute(
        command: list[str], **kwargs: object
    ) -> ProcessExecutionResult:
        if command[0] == "stub-install":
            staged_dir = Path(command[-1])
            (staged_dir / "bin").mkdir(parents=True, exist_ok=True)
            (staged_dir / "bin" / provider.executable_name).write_text(
                "", encoding="utf-8"
            )
            return ProcessExecutionResult(
                command=command,
                exit_code=0,
                stdout="",
                stderr="",
                duration_seconds=0,
            )
        return ProcessExecutionResult(
            command=command,
            exit_code=0,
            stdout="1.0.0",
            stderr="",
            duration_seconds=0,
        )

    monkeypatch.setattr(
        "orcheo.external_agents.runtime.execute_process",
        fake_execute,
    )

    runtime, updated_manifest = await manager._install_latest_locked(
        provider,
        base_manifest,
    )

    assert updated_manifest.previous_version == "0.9.0"
    assert runtime.version == "1.0.0"


@pytest.mark.asyncio
async def test_install_latest_locked_reuses_existing_final_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = StubInstallProvider()
    manager = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        providers={provider.name: provider},
    )
    final_dir = tmp_path / provider.name / "runtimes" / "1.0.0"
    (final_dir / "bin").mkdir(parents=True, exist_ok=True)
    (final_dir / "bin" / provider.executable_name).write_text("", encoding="utf-8")

    async def fake_execute(
        command: list[str], **kwargs: object
    ) -> ProcessExecutionResult:
        if command[0] == "stub-install":
            staged_dir = Path(command[-1])
            (staged_dir / "bin").mkdir(parents=True, exist_ok=True)
            (staged_dir / "bin" / provider.executable_name).write_text(
                "", encoding="utf-8"
            )
            return ProcessExecutionResult(
                command=command,
                exit_code=0,
                stdout="",
                stderr="",
                duration_seconds=0,
            )
        return ProcessExecutionResult(
            command=command,
            exit_code=0,
            stdout="1.0.0",
            stderr="",
            duration_seconds=0,
        )

    monkeypatch.setattr("orcheo.external_agents.runtime.execute_process", fake_execute)

    runtime, _ = await manager._install_latest_locked(provider, None)

    assert runtime.install_dir == final_dir
    assert runtime.executable_path == final_dir / "bin" / provider.executable_name


def test_cleanup_superseded_runtimes_handles_missing_runtime_directory(
    tmp_path: Path,
) -> None:
    provider = FakeProvider()
    manager = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        providers={provider.name: provider},
    )
    manifest = RuntimeManifest(
        provider=provider.name,
        provider_root=tmp_path / provider.name,
        current_version="keep",
        current_runtime_path=tmp_path / provider.name / "runtimes" / "keep",
    )

    manager._cleanup_superseded_runtimes(provider.name, manifest)


def test_cleanup_superseded_runtimes_ignores_non_directory_children(
    tmp_path: Path,
) -> None:
    provider = FakeProvider()
    manager = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        providers={provider.name: provider},
    )
    provider_dir = tmp_path / provider.name / "runtimes"
    keep = provider_dir / "keep"
    keep.mkdir(parents=True)
    stray_file = provider_dir / "README.txt"
    stray_file.write_text("keep me", encoding="utf-8")
    manifest = RuntimeManifest(
        provider=provider.name,
        provider_root=tmp_path / provider.name,
        current_version="keep",
        current_runtime_path=keep,
    )

    manager._cleanup_superseded_runtimes(provider.name, manifest)

    assert stray_file.exists()


def test_cleanup_superseded_runtimes_retains_current_and_previous(
    tmp_path: Path,
) -> None:
    provider = FakeProvider()
    manager = ExternalAgentRuntimeManager(
        runtime_root=tmp_path,
        providers={provider.name: provider},
    )
    provider_dir = tmp_path / provider.name / "runtimes"
    keep = provider_dir / "keep"
    keep.mkdir(parents=True)
    extra = provider_dir / "extra"
    extra.mkdir()
    manifest = RuntimeManifest(
        provider=provider.name,
        provider_root=tmp_path / provider.name,
        current_version="keep",
        current_runtime_path=keep,
        previous_version="prev",
        previous_runtime_path=keep,
    )

    manager._cleanup_superseded_runtimes(provider.name, manifest)
    assert extra.exists() is False
    assert keep.exists()


def test_load_provider_environment_requires_dict(tmp_path: Path) -> None:
    manager = ExternalAgentRuntimeManager(runtime_root=tmp_path)
    env_path = provider_environment_path(tmp_path, "codex")
    env_path.parent.mkdir(parents=True)
    env_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="Persisted environment"):
        manager._load_provider_environment("codex")


class StubInstallProvider(NpmCliProvider):
    name = "stub"
    display_name = "Stub"
    package_name = "@tests/stub"
    executable_name = "stub"

    def install_command(self, install_prefix: Path) -> list[str]:
        return ["stub-install", str(install_prefix)]

    def version_command(self, runtime: ResolvedRuntime) -> list[str]:
        return ["stub-version"]
