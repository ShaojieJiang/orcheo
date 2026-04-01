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
    ProviderLockUnavailableError,
    ResolvedRuntime,
    RuntimeInstallError,
    RuntimeManifest,
    WorkingDirectoryValidationError,
)
from orcheo.external_agents.paths import (
    default_runtime_root,
    validate_working_directory,
)
from orcheo.external_agents.providers.base import NpmCliProvider
from orcheo.external_agents.providers.claude_code import ClaudeCodeProvider
from orcheo.external_agents.providers.codex import CodexProvider
from orcheo.external_agents.runtime import ExternalAgentRuntimeManager


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

    auth_dir = tmp_path / ".codex"
    auth_dir.mkdir()
    (auth_dir / "auth.json").write_text("{}", encoding="utf-8")
    cached_codex = codex.probe_auth(runtime, environ={})
    assert cached_codex.status == AuthStatus.AUTHENTICATED

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
