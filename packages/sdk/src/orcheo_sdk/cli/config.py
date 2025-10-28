"""Configuration helpers for the Orcheo CLI."""

from __future__ import annotations
import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


_DEFAULT_API_URL = "http://localhost:8000"


@dataclass(slots=True)
class ProfileConfig:
    """Configuration declared within a named CLI profile."""

    api_url: str | None = None
    service_token: str | None = None


@dataclass(slots=True)
class CLISettings:
    """Resolved CLI configuration after applying precedence rules."""

    api_url: str
    service_token: str | None
    profile: str | None
    config_path: Path
    cache_dir: Path


class ProfileNotFoundError(ValueError):
    """Raised when a requested profile cannot be located."""


def _default_config_path() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "orcheo" / "cli.toml"


def _default_cache_dir() -> Path:
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache_home / "orcheo"


def load_profiles(path: Path) -> Mapping[str, ProfileConfig]:
    """Return profiles defined in the provided configuration file."""
    if not path.exists():
        return {}

    with path.open("rb") as handle:
        data = tomllib.load(handle)

    raw_profiles = data.get("profiles", {})
    profiles: dict[str, ProfileConfig] = {}
    for name, payload in raw_profiles.items():
        if not isinstance(payload, dict):
            continue
        profiles[name] = ProfileConfig(
            api_url=payload.get("api_url"),
            service_token=payload.get("service_token"),
        )
    return profiles


def resolve_settings(
    *,
    api_url: str | None,
    service_token: str | None,
    profile: str | None,
    config_path: Path | None,
    cache_dir: Path | None,
    env: Mapping[str, str] | None = None,
) -> CLISettings:
    """Combine CLI options, environment variables, and profiles."""
    env = dict(env or {})

    profile_name = profile or env.get("ORCHEO_PROFILE")
    resolved_config_path = config_path or Path(
        env.get("ORCHEO_CLI_CONFIG", _default_config_path())
    )
    resolved_cache_dir = cache_dir or Path(
        env.get("ORCHEO_CLI_CACHE", _default_cache_dir())
    )

    profiles = load_profiles(resolved_config_path)
    profile_config: ProfileConfig | None = None
    if profile_name:
        profile_config = profiles.get(profile_name)
        if profile_config is None:
            msg = f"Profile '{profile_name}' not found in {resolved_config_path}"
            raise ProfileNotFoundError(msg)

    resolved_api_url = (
        api_url
        or env.get("ORCHEO_API_URL")
        or (profile_config.api_url if profile_config else None)
        or _DEFAULT_API_URL
    )

    resolved_service_token = (
        service_token
        or env.get("ORCHEO_SERVICE_TOKEN")
        or (profile_config.service_token if profile_config else None)
    )

    return CLISettings(
        api_url=resolved_api_url,
        service_token=resolved_service_token,
        profile=profile_name,
        config_path=resolved_config_path,
        cache_dir=resolved_cache_dir,
    )


__all__ = [
    "CLISettings",
    "ProfileConfig",
    "ProfileNotFoundError",
    "load_profiles",
    "resolve_settings",
]
