"""CLI update check helpers."""

from __future__ import annotations
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from typing import Any
from packaging.version import InvalidVersion, Version
from rich.console import Console
from orcheo_sdk.cli.cache import CacheManager
from orcheo_sdk.cli.http import ApiClient


_CHECK_CACHE_PREFIX = "update_check"
_UPDATE_CHECK_TTL_HOURS = 24


@dataclass(slots=True)
class UpdateAdvice:
    """Derived update availability status."""

    cli_update_available: bool
    backend_update_available: bool
    message_lines: list[str]


def _is_stable(version_value: str | None) -> bool:
    if not version_value:
        return False
    try:
        parsed = Version(version_value)
    except InvalidVersion:
        return False
    return not (parsed.is_prerelease or parsed.is_devrelease or parsed.local)


def _compare_versions(current: str | None, latest: str | None) -> bool:
    if not (current and latest):
        return False
    if not _is_stable(current):
        return False
    try:
        return Version(latest) > Version(current)
    except InvalidVersion:
        return False


def _read_cli_version() -> str | None:
    try:
        return package_version("orcheo-sdk")
    except PackageNotFoundError:
        return None


def _cache_key(profile: str | None, api_url: str) -> str:
    payload = f"{profile or 'default'}::{api_url}".encode()
    digest = hashlib.sha256(payload).hexdigest()[:16]
    return f"{_CHECK_CACHE_PREFIX}_{digest}"


def _read_ttl() -> timedelta:
    return timedelta(hours=_UPDATE_CHECK_TTL_HOURS)


def should_check(cache: CacheManager, *, profile: str | None, api_url: str) -> bool:
    """Return whether the update check window has elapsed."""
    entry = cache.load(_cache_key(profile, api_url))
    if entry is None:
        return True
    return datetime.now(tz=UTC) - entry.timestamp >= _read_ttl()


def evaluate_update_advice(payload: dict[str, Any]) -> UpdateAdvice:
    """Build reminder text from backend metadata payload."""
    cli_current = _read_cli_version()
    cli_latest = payload.get("cli", {}).get("latest_version")
    backend_current = payload.get("backend", {}).get("current_version")
    backend_latest = payload.get("backend", {}).get("latest_version")

    cli_update = _compare_versions(cli_current, cli_latest)
    backend_update = _compare_versions(backend_current, backend_latest)

    lines: list[str] = []
    if cli_update:
        lines.append(
            "CLI update available: "
            f"{cli_current} -> {cli_latest} "
            "(run: uv tool upgrade orcheo-sdk)"
        )
    if backend_update:
        lines.append(
            "Backend update available: "
            f"{backend_current} -> {backend_latest} "
            "(run: orcheo install upgrade)"
        )

    minimum_cli = payload.get("cli", {}).get("minimum_recommended_version")
    minimum_backend = payload.get("backend", {}).get("minimum_recommended_version")
    if minimum_cli:
        lines.append(f"Recommended minimum CLI version: {minimum_cli}")
    if minimum_backend:
        lines.append(f"Recommended minimum backend version: {minimum_backend}")

    cli_notes = payload.get("cli", {}).get("release_notes_url")
    backend_notes = payload.get("backend", {}).get("release_notes_url")
    if cli_notes:
        lines.append(f"CLI release notes: {cli_notes}")
    if backend_notes:
        lines.append(f"Backend release notes: {backend_notes}")

    return UpdateAdvice(
        cli_update_available=cli_update,
        backend_update_available=backend_update,
        message_lines=lines,
    )


def maybe_print_update_notice(
    *,
    cache: CacheManager,
    client: ApiClient,
    profile: str | None,
    console: Console,
) -> None:
    """Run a soft-fail update check and print concise reminders."""
    key = _cache_key(profile, client.base_url)
    if not should_check(cache, profile=profile, api_url=client.base_url):
        return

    try:
        payload_raw = client.get("/api/system/info")
        payload = payload_raw if isinstance(payload_raw, dict) else {}
        advice = evaluate_update_advice(payload)
        if advice.message_lines:
            console.print("[yellow]Orcheo update reminder:[/yellow]")
            for line in advice.message_lines:
                console.print(f"  - {line}")
    except Exception:
        pass
    finally:
        cache.store(
            key,
            {
                "checked_at": datetime.now(tz=UTC).isoformat(),
                "api_url": client.base_url,
                "profile": profile,
            },
        )


__all__ = [
    "evaluate_update_advice",
    "maybe_print_update_notice",
    "should_check",
]
