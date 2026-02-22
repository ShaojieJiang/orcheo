"""Guided setup and upgrade command for the Orcheo stack."""

from __future__ import annotations
import json
import os
import re
import secrets
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from urllib.request import urlopen
import typer
from rich.console import Console


AuthMode = Literal["api-key", "oauth"]
SetupMode = Literal["install", "upgrade"]
_STACK_ASSET_BASE_URL = (
    "https://raw.githubusercontent.com/ShaojieJiang/orcheo/main/deploy/local-stack"
)
_STACK_ASSET_FILES = (
    "docker-compose.yml",
    "Dockerfile.orcheo",
    ".env.example",
    "chatkit_widgets/Single-choice list.widget",
    "chatkit_widgets/Multi-choice Selector.widget",
)
_CHATKIT_DOMAIN_KEY_PLACEHOLDER = "domain_pk_replace_me"


@dataclass(slots=True)
class SetupConfig:
    """Resolved setup options before execution."""

    mode: SetupMode
    backend_url: str
    auth_mode: AuthMode
    api_key: str | None
    chatkit_domain_key: str | None
    start_local_stack: bool
    install_docker_if_missing: bool
    local_stack_project_dir: str | None = None
    local_stack_env_file: str | None = None


def _run_command(command: list[str], *, console: Console) -> None:
    command_text = " ".join(command)
    console.print(f"[cyan]$ {command_text}[/cyan]")
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise typer.BadParameter(
            f"Command failed with exit code {result.returncode}: {command_text}"
        )


def _has_binary(name: str) -> bool:
    return shutil.which(name) is not None


def _resolve_mode(mode: SetupMode | None, *, yes: bool) -> SetupMode:
    if mode is not None:
        return mode
    if yes:
        return "install"
    selected = typer.prompt("Setup mode [install/upgrade]", default="install").strip()
    return "upgrade" if selected == "upgrade" else "install"


def _resolve_backend_url(backend_url: str | None, *, yes: bool) -> str:
    if backend_url:
        return backend_url
    if yes:
        return "http://localhost:8000"
    return typer.prompt("Backend URL", default="http://localhost:8000")


def _resolve_auth_mode(auth_mode: AuthMode | None, *, yes: bool) -> AuthMode:
    if auth_mode is not None:
        return auth_mode
    if yes:
        return "api-key"
    selected = typer.prompt("Auth mode [api-key/oauth]", default="api-key").strip()
    return "oauth" if selected == "oauth" else "api-key"


def _resolve_bool(
    explicit: bool | None,
    *,
    yes_default: bool,
    prompt: str,
    default: bool,
) -> bool:
    if explicit is not None:
        return explicit
    if yes_default:
        return default
    return typer.confirm(prompt, default=default)


def _resolve_api_key(
    auth_mode: AuthMode,
    api_key: str | None,
    *,
    mode: SetupMode,
    manual: bool,
) -> str | None:
    if auth_mode != "api-key":
        return None
    if api_key:
        return api_key
    if mode == "upgrade":
        if manual:
            provided = typer.prompt(
                "Enter API key (Enter to keep existing)",
                default="",
                show_default=False,
                hide_input=True,
            ).strip()
            return provided or None
        return None
    if manual:
        return typer.prompt("Enter API key", hide_input=True)
    return secrets.token_urlsafe(32)


def _normalize_optional_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _resolve_chatkit_domain_key(
    chatkit_domain_key: str | None,
    *,
    yes: bool,
) -> str | None:
    resolved = _normalize_optional_value(chatkit_domain_key)
    if resolved is not None:
        return resolved
    if yes:
        return None
    return _normalize_optional_value(
        typer.prompt(
            "ChatKit domain key (VITE_ORCHEO_CHATKIT_DOMAIN_KEY, Enter to skip)",
            default="",
            show_default=False,
        )
    )


def _resolve_stack_project_dir() -> Path:
    configured = os.getenv("ORCHEO_STACK_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".orcheo" / "stack"


def _resolve_stack_asset_base_url() -> str:
    configured = os.getenv("ORCHEO_STACK_ASSET_BASE_URL")
    if configured:
        return configured.rstrip("/")
    return _STACK_ASSET_BASE_URL


def _download_stack_asset(relative_path: str, *, console: Console) -> bytes:
    asset_url = f"{_resolve_stack_asset_base_url()}/{quote(relative_path, safe='/')}"
    console.print(f"[cyan]Fetching local stack asset: {relative_path}[/cyan]")
    try:
        with urlopen(asset_url, timeout=30) as response:  # noqa: S310
            return response.read()
    except OSError as exc:
        raise typer.BadParameter(
            "Failed to download local stack asset "
            f"'{relative_path}' from {asset_url}: {exc}"
        ) from exc


def _sync_stack_asset(relative_path: str, stack_dir: Path, *, console: Console) -> None:
    destination = stack_dir / relative_path
    remote_payload = _download_stack_asset(relative_path, console=console)

    if destination.exists():
        local_payload = destination.read_bytes()
        if local_payload == remote_payload:
            return
        destination.write_bytes(remote_payload)
        console.print(f"[green]Updated local stack asset: {relative_path}[/green]")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(remote_payload)
    console.print(f"[green]Downloaded local stack asset: {relative_path}[/green]")


_ENV_KEY_PATTERN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")


def _build_env_updates(
    config: SetupConfig,
) -> tuple[dict[str, str], dict[str, str]]:
    """Return ``(updates, defaults)`` for .env upsert.

    ``updates`` are always applied.  ``defaults`` contain auto-generated
    secrets that should only be written to a freshly-created .env file.
    """
    updates: dict[str, str] = {
        "ORCHEO_API_URL": config.backend_url,
        "VITE_ORCHEO_BACKEND_URL": config.backend_url,
        "ORCHEO_AUTH_MODE": "required",
    }
    if config.auth_mode == "api-key" and config.api_key:
        updates["ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN"] = config.api_key
    elif config.auth_mode == "oauth":
        updates["ORCHEO_AUTH_BOOTSTRAP_SERVICE_TOKEN"] = ""
    if config.chatkit_domain_key:
        updates["VITE_ORCHEO_CHATKIT_DOMAIN_KEY"] = config.chatkit_domain_key

    defaults: dict[str, str] = {
        "ORCHEO_POSTGRES_PASSWORD": secrets.token_urlsafe(16),
        "ORCHEO_VAULT_ENCRYPTION_KEY": secrets.token_hex(32),
        "ORCHEO_CHATKIT_TOKEN_SIGNING_KEY": secrets.token_urlsafe(32),
    }
    return updates, defaults


def _read_env_value(env_file: Path, key: str) -> str | None:
    for line in env_file.read_text(encoding="utf-8").splitlines():
        match = _ENV_KEY_PATTERN.match(line)
        if not match or match.group(1) != key:
            continue
        _, _, value = line.partition("=")
        stripped = value.strip()
        return stripped or None
    return None


def _warn_chatkit_domain_key_missing(*, env_file: Path, console: Console) -> None:
    configured_value = _read_env_value(env_file, "VITE_ORCHEO_CHATKIT_DOMAIN_KEY")
    if configured_value and configured_value != _CHATKIT_DOMAIN_KEY_PLACEHOLDER:
        return
    console.print(
        "[yellow]ChatKit domain key is not configured. ChatKit UI features will not "
        "work until VITE_ORCHEO_CHATKIT_DOMAIN_KEY is set in "
        f"{env_file}. You can rerun setup with --chatkit-domain-key.[/yellow]"
    )


def _upsert_env_values(
    env_file: Path,
    updates: dict[str, str],
    *,
    defaults: dict[str, str] | None = None,
    console: Console,
) -> None:
    """Upsert environment values into the .env file.

    Keys in *updates* always overwrite existing values.  Keys in *defaults*
    only overwrite when the key is already present in the file; missing keys
    are appended.
    """
    original = env_file.read_text(encoding="utf-8")
    lines = original.splitlines()
    pending_updates = dict(updates)
    pending_defaults = dict(defaults or {})
    rewritten: list[str] = []

    for line in lines:
        match = _ENV_KEY_PATTERN.match(line)
        if not match:
            rewritten.append(line)
            continue

        key = match.group(1)
        if key in pending_updates:
            rewritten.append(f"{key}={pending_updates.pop(key)}")
        elif key in pending_defaults:
            rewritten.append(f"{key}={pending_defaults.pop(key)}")
        else:
            rewritten.append(line)

    for key, value in pending_updates.items():
        rewritten.append(f"{key}={value}")
    for key, value in pending_defaults.items():
        rewritten.append(f"{key}={value}")

    updated = "\n".join(rewritten)
    if updated:
        updated += "\n"
    if updated == original:
        return

    env_file.write_text(updated, encoding="utf-8")
    console.print(f"[green]Updated local stack env file at {env_file}[/green]")


def _ensure_local_stack_assets(
    *, config: SetupConfig, console: Console
) -> tuple[Path, Path]:
    stack_dir = _resolve_stack_project_dir()
    stack_dir.mkdir(parents=True, exist_ok=True)

    for relative_path in _STACK_ASSET_FILES:
        _sync_stack_asset(relative_path, stack_dir, console=console)

    env_file = stack_dir / ".env"
    env_created = not env_file.exists()
    if env_created:
        env_template = stack_dir / ".env.example"
        if not env_template.exists():
            _sync_stack_asset(".env.example", stack_dir, console=console)
        shutil.copyfile(env_template, env_file)
        console.print(f"[green]Created local stack env file at {env_file}[/green]")

    updates, defaults = _build_env_updates(config)
    if env_created:
        # Fresh install: overwrite template placeholders with generated secrets.
        _upsert_env_values(env_file, updates, defaults=defaults, console=console)
    else:
        # Existing .env: apply config updates only, preserve user secrets.
        _upsert_env_values(env_file, updates, console=console)
        # Backfill ChatKit key for legacy env files so compose startup is not blocked.
        if _read_env_value(env_file, "VITE_ORCHEO_CHATKIT_DOMAIN_KEY") is None:
            _upsert_env_values(
                env_file,
                {"VITE_ORCHEO_CHATKIT_DOMAIN_KEY": _CHATKIT_DOMAIN_KEY_PLACEHOLDER},
                console=console,
            )
    return stack_dir, env_file


def run_setup(
    *,
    mode: SetupMode | None,
    backend_url: str | None,
    auth_mode: AuthMode | None,
    api_key: str | None,
    chatkit_domain_key: str | None,
    start_local_stack: bool | None,
    install_docker: bool | None,
    yes: bool,
    manual_secrets: bool,
    console: Console,
) -> SetupConfig:
    """Collect interactive/non-interactive setup options."""
    resolved_mode = _resolve_mode(mode, yes=yes)
    resolved_backend_url = _resolve_backend_url(backend_url, yes=yes)
    resolved_auth_mode = _resolve_auth_mode(auth_mode, yes=yes)
    resolved_start_local_stack = _resolve_bool(
        start_local_stack,
        yes_default=yes,
        prompt="Start local stack with docker compose after install?",
        default=True,
    )
    resolved_install_docker = _resolve_bool(
        install_docker,
        yes_default=yes,
        prompt="Install Docker when missing?",
        default=True,
    )

    resolved_api_key = _resolve_api_key(
        resolved_auth_mode,
        api_key,
        mode=resolved_mode,
        manual=manual_secrets,
    )
    resolved_chatkit_domain_key = _resolve_chatkit_domain_key(
        chatkit_domain_key, yes=yes
    )

    if resolved_api_key and not manual_secrets and not yes:
        console.print("[green]Generated API key locally.[/green]")
    if (
        resolved_mode == "upgrade"
        and resolved_auth_mode == "api-key"
        and resolved_api_key is None
    ):
        console.print(
            "[cyan]Keeping existing API bootstrap token. "
            "Pass --api-key to rotate it.[/cyan]"
        )
    if resolved_auth_mode == "oauth":
        console.print(
            "[yellow]OAuth mode selected. Configure ORCHEO_AUTH_ISSUER, "
            "ORCHEO_AUTH_AUDIENCE, ORCHEO_AUTH_JWKS_URL, and matching "
            "VITE_ORCHEO_AUTH_* values in your stack .env.[/yellow]"
        )

    return SetupConfig(
        mode=resolved_mode,
        backend_url=resolved_backend_url,
        auth_mode=resolved_auth_mode,
        api_key=resolved_api_key,
        chatkit_domain_key=resolved_chatkit_domain_key,
        start_local_stack=resolved_start_local_stack,
        install_docker_if_missing=resolved_install_docker,
    )


_HEALTH_POLL_INTERVAL_SECONDS = 5
_DEFAULT_HEALTH_POLL_TIMEOUT_SECONDS = 60


def _read_health_poll_timeout_seconds() -> int:
    raw = os.getenv("ORCHEO_SETUP_HEALTH_POLL_TIMEOUT_SECONDS")
    if not raw:
        return _DEFAULT_HEALTH_POLL_TIMEOUT_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_HEALTH_POLL_TIMEOUT_SECONDS
    if value < 0:
        return _DEFAULT_HEALTH_POLL_TIMEOUT_SECONDS
    return value


def _poll_backend_health(
    backend_url: str,
    *,
    console: Console,
) -> bool:
    """Poll the backend until it responds or the timeout expires."""
    health_url = f"{backend_url.rstrip('/')}/api/system/health"
    timeout_seconds = _read_health_poll_timeout_seconds()
    console.print(
        f"[cyan]Waiting for backend at {health_url} "
        f"(up to {timeout_seconds}s)...[/cyan]"
    )
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=_HEALTH_POLL_INTERVAL_SECONDS) as resp:  # noqa: S310
                if resp.status == 200:
                    console.print("[green]Backend is healthy.[/green]")
                    return True
        except OSError:
            pass
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(_HEALTH_POLL_INTERVAL_SECONDS, remaining))
    return False


def execute_setup(config: SetupConfig, *, console: Console) -> None:
    """Run setup/upgrade actions based on the selected options."""
    stack_dir, env_file = _ensure_local_stack_assets(config=config, console=console)
    config.local_stack_project_dir = str(stack_dir)
    config.local_stack_env_file = str(env_file)
    _warn_chatkit_domain_key_missing(env_file=env_file, console=console)

    if config.start_local_stack and not _has_binary("docker"):
        if config.install_docker_if_missing:
            console.print(
                "[yellow]Docker is missing and automatic installation is not "
                "available yet. Continuing without starting the local stack. "
                "Install Docker Desktop (https://docs.docker.com/get-docker/) "
                "and rerun with --start-local-stack.[/yellow]"
            )
            config.start_local_stack = False
        else:
            raise typer.BadParameter(
                "Docker is required to start the local stack, and you chose "
                "--skip-docker-install. Install Docker and rerun setup."
            )

    if config.start_local_stack and _has_binary("docker"):
        compose_args = [
            "docker",
            "compose",
            "-f",
            str(stack_dir / "docker-compose.yml"),
            "--project-directory",
            str(stack_dir),
        ]

        if config.mode == "upgrade":
            _run_command([*compose_args, "build", "--no-cache"], console=console)
            _run_command([*compose_args, "up", "-d"], console=console)
        else:
            _run_command([*compose_args, "up", "-d", "--build"], console=console)

        if not _poll_backend_health(config.backend_url, console=console):
            compose_file = stack_dir / "docker-compose.yml"
            timeout_seconds = _read_health_poll_timeout_seconds()
            console.print(
                "[yellow]Backend did not become healthy within "
                f"{timeout_seconds} seconds.\n"
                "Check service logs with:[/yellow]\n"
                f"  docker compose -f {compose_file} logs"
            )


def print_summary(config: SetupConfig, *, console: Console) -> None:
    """Print setup summary with versions and next steps."""
    summary = {
        "mode": config.mode,
        "backend_url": config.backend_url,
        "auth_mode": config.auth_mode,
        "stack_assets_synced": True,
        "local_stack_started": config.start_local_stack,
        "local_stack_project_dir": config.local_stack_project_dir,
        "local_stack_env_file": config.local_stack_env_file,
        "completed_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
    }

    console.print("\n[bold green]Setup complete[/bold green]")
    console.print_json(json.dumps(summary))

    if config.start_local_stack:
        console.print(
            "\n[yellow]Note:[/yellow] Canvas may take 2-3 minutes on first "
            "startup while npm installs dependencies."
        )

    console.print("\nNext steps:")
    console.print(
        "  1. Run [cyan]orcheo auth login[/cyan] (or configure a service token)."
    )
    console.print("  2. Run [cyan]orcheo workflow list[/cyan] to verify connectivity.")


__all__ = [
    "AuthMode",
    "SetupConfig",
    "SetupMode",
    "execute_setup",
    "print_summary",
    "run_setup",
]
