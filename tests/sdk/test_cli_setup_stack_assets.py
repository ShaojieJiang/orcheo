"""Tests for local-stack bootstrap assets in `orcheo install`."""

from __future__ import annotations
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import unquote
import pytest
import typer
from rich.console import Console
from orcheo_sdk.cli.setup import SetupConfig, execute_setup, run_setup


def test_default_stack_asset_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ORCHEO_STACK_ASSET_BASE_URL", raising=False)
    from orcheo_sdk.cli import setup as setup_mod

    assert (
        setup_mod._resolve_stack_asset_base_url()
        == "https://raw.githubusercontent.com/ShaojieJiang/orcheo/main/deploy/local-stack"
    )


class _Response:
    def __init__(self, payload: bytes, *, status: int = 200) -> None:
        self._buffer = BytesIO(payload)
        self.status = status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._buffer.read()


_ENV_EXAMPLE = (
    b"ORCHEO_POSTGRES_PASSWORD=change-me\n"
    b"ORCHEO_VAULT_ENCRYPTION_KEY=replace-with-64-hex-chars\n"
    b"ORCHEO_CHATKIT_TOKEN_SIGNING_KEY=strong-random-secret\n"
    b"VITE_ORCHEO_CHATKIT_DOMAIN_KEY=domain_pk_replace_me\n"
)


def _default_assets() -> dict[str, bytes]:
    return {
        "docker-compose.yml": b"services: {}\n",
        "Dockerfile.orcheo": b"FROM python:3.12-slim\n",
        ".env.example": _ENV_EXAMPLE,
        "chatkit_widgets/Single-choice list.widget": b"single",
        "chatkit_widgets/Multi-choice Selector.widget": b"multi",
    }


def _setup_config() -> SetupConfig:
    return SetupConfig(
        mode="install",
        backend_url="http://localhost:8000",
        auth_mode="api-key",
        api_key="generated",
        chatkit_domain_key=None,
        start_local_stack=True,
        install_docker_if_missing=True,
    )


def _patch_common(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stack_dir: Path,
    base_url: str = "https://example.test/assets",
    assets: dict[str, bytes] | None = None,
    has_docker: bool = True,
    commands: list[list[str]] | None = None,
    health_ok: bool = True,
) -> None:
    """Wire up common monkeypatches for execute_setup tests."""
    resolved_assets = assets or _default_assets()
    monkeypatch.setenv("ORCHEO_STACK_DIR", str(stack_dir))
    monkeypatch.setenv("ORCHEO_STACK_ASSET_BASE_URL", base_url)
    monkeypatch.setattr(
        "orcheo_sdk.cli.setup._has_binary",
        lambda name: has_docker and name in {"docker"},
    )

    def _run_command(command: list[str], *, console: Console) -> None:
        del console
        if commands is not None:
            commands.append(command)

    monkeypatch.setattr("orcheo_sdk.cli.setup._run_command", _run_command)
    monkeypatch.setattr(
        "orcheo_sdk.cli.setup._poll_backend_health",
        lambda backend_url, *, console: health_ok,
    )

    def _urlopen(url: str, timeout: int) -> _Response:
        del timeout
        relative_path = unquote(url.removeprefix(f"{base_url}/"))
        return _Response(resolved_assets[relative_path])

    monkeypatch.setattr("orcheo_sdk.cli.setup.urlopen", _urlopen)


def test_execute_setup_bootstraps_stack_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stack_dir = tmp_path / "stack"
    commands: list[list[str]] = []
    _patch_common(monkeypatch, stack_dir=stack_dir, commands=commands)

    config = _setup_config()
    execute_setup(config, console=Console(record=True))

    assert commands[0] == [
        "docker",
        "compose",
        "-f",
        str(stack_dir / "docker-compose.yml"),
        "--project-directory",
        str(stack_dir),
        "up",
        "-d",
        "--build",
    ]
    assert config.local_stack_project_dir == str(stack_dir)
    assert config.local_stack_env_file == str(stack_dir / ".env")

    assert (stack_dir / "docker-compose.yml").exists()
    assert (stack_dir / "Dockerfile.orcheo").exists()
    assert (stack_dir / ".env.example").exists()
    assert (stack_dir / "chatkit_widgets/Single-choice list.widget").exists()
    assert (stack_dir / "chatkit_widgets/Multi-choice Selector.widget").exists()

    env_content = (stack_dir / ".env").read_text(encoding="utf-8")
    assert "ORCHEO_API_URL=http://localhost:8000" in env_content
    assert "VITE_ORCHEO_BACKEND_URL=http://localhost:8000" in env_content
    assert "ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN=generated" in env_content


def test_execute_setup_upgrade_rebuilds_without_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stack_dir = tmp_path / "stack"
    commands: list[list[str]] = []
    _patch_common(monkeypatch, stack_dir=stack_dir, commands=commands)

    config = _setup_config()
    config.mode = "upgrade"
    execute_setup(config, console=Console(record=True))

    assert commands[0] == [
        "docker",
        "compose",
        "-f",
        str(stack_dir / "docker-compose.yml"),
        "--project-directory",
        str(stack_dir),
        "build",
        "--no-cache",
    ]
    assert commands[1] == [
        "docker",
        "compose",
        "-f",
        str(stack_dir / "docker-compose.yml"),
        "--project-directory",
        str(stack_dir),
        "up",
        "-d",
    ]


def test_execute_setup_generates_secrets_on_fresh_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fresh install should replace template placeholders with real secrets."""
    stack_dir = tmp_path / "stack"
    _patch_common(monkeypatch, stack_dir=stack_dir, has_docker=False)

    config = _setup_config()
    config.start_local_stack = False
    execute_setup(config, console=Console(record=True))

    env_content = (stack_dir / ".env").read_text(encoding="utf-8")
    # Placeholders must be gone.
    assert "change-me" not in env_content
    assert "replace-with-64-hex-chars" not in env_content
    assert "strong-random-secret" not in env_content
    # Keys must still exist with generated values.
    assert "ORCHEO_POSTGRES_PASSWORD=" in env_content
    assert "ORCHEO_VAULT_ENCRYPTION_KEY=" in env_content
    assert "ORCHEO_CHATKIT_TOKEN_SIGNING_KEY=" in env_content
    # VITE_ORCHEO_CHATKIT_DOMAIN_KEY is NOT auto-generated.
    assert "VITE_ORCHEO_CHATKIT_DOMAIN_KEY=domain_pk_replace_me" in env_content


def test_run_setup_upgrade_preserves_existing_api_key_by_default() -> None:
    config = run_setup(
        mode="upgrade",
        backend_url=None,
        auth_mode=None,
        api_key=None,
        chatkit_domain_key=None,
        start_local_stack=None,
        install_docker=None,
        yes=True,
        manual_secrets=False,
        console=Console(record=True),
    )

    assert config.mode == "upgrade"
    assert config.auth_mode == "api-key"
    assert config.api_key is None


def test_run_setup_upgrade_honors_explicit_api_key() -> None:
    config = run_setup(
        mode="upgrade",
        backend_url=None,
        auth_mode="api-key",
        api_key="explicit-token",
        chatkit_domain_key=None,
        start_local_stack=None,
        install_docker=None,
        yes=True,
        manual_secrets=False,
        console=Console(record=True),
    )

    assert config.mode == "upgrade"
    assert config.auth_mode == "api-key"
    assert config.api_key == "explicit-token"


def test_execute_setup_preserves_secrets_on_upgrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Existing .env values must not be overwritten on upgrade."""
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir(parents=True)
    # Pre-existing .env with user-customised secrets.
    (stack_dir / ".env").write_text(
        "ORCHEO_POSTGRES_PASSWORD=my-custom-password\n"
        "ORCHEO_VAULT_ENCRYPTION_KEY=aabbccdd\n"
        "ORCHEO_CHATKIT_TOKEN_SIGNING_KEY=my-signing-key\n",
        encoding="utf-8",
    )
    _patch_common(monkeypatch, stack_dir=stack_dir, has_docker=False)

    config = _setup_config()
    config.mode = "upgrade"
    config.start_local_stack = False
    execute_setup(config, console=Console(record=True))

    env_content = (stack_dir / ".env").read_text(encoding="utf-8")
    # Original user values preserved.
    assert "ORCHEO_POSTGRES_PASSWORD=my-custom-password" in env_content
    assert "ORCHEO_VAULT_ENCRYPTION_KEY=aabbccdd" in env_content
    assert "ORCHEO_CHATKIT_TOKEN_SIGNING_KEY=my-signing-key" in env_content
    # Config updates still applied.
    assert "ORCHEO_API_URL=http://localhost:8000" in env_content


def test_execute_setup_raises_when_asset_download_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORCHEO_STACK_DIR", str(tmp_path / "stack"))
    monkeypatch.setattr(
        "orcheo_sdk.cli.setup._has_binary",
        lambda name: name in {"docker"},
    )
    monkeypatch.setattr(
        "orcheo_sdk.cli.setup._run_command",
        lambda command, *, console: None,
    )

    def _urlopen(url: str, timeout: int) -> Any:
        del url, timeout
        raise OSError("network error")

    monkeypatch.setattr("orcheo_sdk.cli.setup.urlopen", _urlopen)

    with pytest.raises(
        typer.BadParameter, match="Failed to download local stack asset"
    ):
        execute_setup(_setup_config(), console=Console(record=True))


def test_execute_setup_updates_different_local_asset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir(parents=True, exist_ok=True)
    (stack_dir / "docker-compose.yml").write_text(
        "services: {old: 1}\n", encoding="utf-8"
    )

    assets = _default_assets()
    assets["docker-compose.yml"] = b"services: {new: 1}\n"
    _patch_common(monkeypatch, stack_dir=stack_dir, assets=assets, has_docker=False)

    config = _setup_config()
    config.start_local_stack = False
    execute_setup(config, console=Console(record=True))

    assert (stack_dir / "docker-compose.yml").read_bytes() == assets[
        "docker-compose.yml"
    ]


def test_poll_backend_health_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Health poll should succeed when the backend responds with 200."""
    from orcheo_sdk.cli.setup import _poll_backend_health

    call_count = {"n": 0}
    captured_url = {"value": ""}

    def _urlopen(url: str, timeout: int) -> _Response:
        captured_url["value"] = url
        del timeout
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise OSError("not ready")
        return _Response(b'{"status":"ok"}', status=200)

    monkeypatch.setattr("orcheo_sdk.cli.setup.urlopen", _urlopen)
    monkeypatch.setattr("orcheo_sdk.cli.setup._HEALTH_POLL_INTERVAL_SECONDS", 0)
    monkeypatch.setattr("orcheo_sdk.cli.setup._HEALTH_POLL_TIMEOUT_SECONDS", 5)

    console = Console(record=True)
    assert _poll_backend_health("http://localhost:8000", console=console)
    output = console.export_text()
    assert "Backend is healthy" in output
    assert captured_url["value"] == "http://localhost:8000/api/system/health"


def test_poll_backend_health_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Health poll should return False when backend never becomes healthy."""
    from orcheo_sdk.cli.setup import _poll_backend_health

    def _urlopen(url: str, timeout: int) -> _Response:
        del url, timeout
        raise OSError("not ready")

    monkeypatch.setattr("orcheo_sdk.cli.setup.urlopen", _urlopen)
    monkeypatch.setattr("orcheo_sdk.cli.setup._HEALTH_POLL_INTERVAL_SECONDS", 0)
    monkeypatch.setattr("orcheo_sdk.cli.setup._HEALTH_POLL_TIMEOUT_SECONDS", 0)

    console = Console(record=True)
    assert not _poll_backend_health("http://localhost:8000", console=console)


def test_execute_setup_prints_health_warning_on_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When backend doesn't come up, setup should print a warning."""
    stack_dir = tmp_path / "stack"
    _patch_common(monkeypatch, stack_dir=stack_dir, health_ok=False)

    config = _setup_config()
    console = Console(record=True)
    execute_setup(config, console=console)

    output = console.export_text()
    assert "did not become healthy" in output
    assert "docker compose" in output


def test_execute_setup_skips_stack_start_when_docker_missing_and_install_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stack_dir = tmp_path / "stack"
    _patch_common(monkeypatch, stack_dir=stack_dir, has_docker=False)

    config = _setup_config()
    config.install_docker_if_missing = True
    console = Console(record=True)
    execute_setup(config, console=console)

    assert config.start_local_stack is False
    assert "automatic installation is not available yet" in console.export_text()


def test_execute_setup_raises_when_docker_missing_and_install_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stack_dir = tmp_path / "stack"
    _patch_common(monkeypatch, stack_dir=stack_dir, has_docker=False)

    config = _setup_config()
    config.install_docker_if_missing = False
    with pytest.raises(typer.BadParameter, match="--skip-docker-install"):
        execute_setup(config, console=Console(record=True))


def test_execute_setup_warns_when_chatkit_domain_key_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stack_dir = tmp_path / "stack"
    _patch_common(monkeypatch, stack_dir=stack_dir, has_docker=False)

    config = _setup_config()
    config.start_local_stack = False
    console = Console(record=True)
    execute_setup(config, console=console)

    assert "ChatKit domain key is not configured" in console.export_text()


def test_execute_setup_backfills_chatkit_domain_key_when_missing_in_existing_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir(parents=True, exist_ok=True)
    (stack_dir / ".env").write_text(
        "ORCHEO_POSTGRES_PASSWORD=my-custom-password\n",
        encoding="utf-8",
    )
    _patch_common(monkeypatch, stack_dir=stack_dir, has_docker=False)

    config = _setup_config()
    config.start_local_stack = False
    execute_setup(config, console=Console(record=True))

    env_content = (stack_dir / ".env").read_text(encoding="utf-8")
    assert "VITE_ORCHEO_CHATKIT_DOMAIN_KEY=domain_pk_replace_me" in env_content


def test_execute_setup_clears_bootstrap_token_for_oauth_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stack_dir = tmp_path / "stack"
    stack_dir.mkdir(parents=True, exist_ok=True)
    (stack_dir / ".env").write_text(
        "ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN=legacy-token\n",
        encoding="utf-8",
    )
    _patch_common(monkeypatch, stack_dir=stack_dir, has_docker=False)

    config = _setup_config()
    config.auth_mode = "oauth"
    config.api_key = None
    config.start_local_stack = False
    execute_setup(config, console=Console(record=True))

    env_content = (stack_dir / ".env").read_text(encoding="utf-8")
    assert "ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN=\n" in env_content
