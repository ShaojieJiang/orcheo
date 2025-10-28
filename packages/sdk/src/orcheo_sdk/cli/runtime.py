"""Runtime helpers shared across CLI commands."""

from __future__ import annotations
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
import httpx
from rich.console import Console


DEFAULT_API_URL = "http://localhost:8000"
CONFIG_ENV_VAR = "ORCHEO_PROFILE"
CACHE_ENV_VAR = "ORCHEO_CACHE_DIR"
CONFIG_PATH_ENV_VAR = "ORCHEO_CONFIG_PATH"
CACHE_DEFAULT_TTL = timedelta(hours=24)
USER_AGENT = "orcheo-cli/0.1"


class CliError(RuntimeError):
    """Raised when the CLI cannot complete an operation."""


@dataclass(slots=True)
class CliSettings:
    """Resolved configuration for a CLI invocation."""

    api_url: str = DEFAULT_API_URL
    service_token: str | None = None
    profile: str | None = None
    timeout: float = 30.0


@dataclass(slots=True)
class CacheEntry:
    """Entry read from the on-disk cache."""

    data: Any
    cached_at: datetime

    @property
    def age(self) -> timedelta:
        """Return how long ago the cache entry was stored."""
        return datetime.now(tz=UTC) - self.cached_at


class CacheStore:
    """Simple JSON cache used for offline mode."""

    def __init__(self, base_path: Path, *, ttl: timedelta = CACHE_DEFAULT_TTL) -> None:
        """Create a cache store backed by ``base_path``."""
        self.base_path = base_path
        self.ttl = ttl
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _entry_path(self, key: str) -> Path:
        """Return the filesystem path for ``key``."""
        slug = key.replace("/", "_").replace("::", "_")
        return self.base_path / f"{slug}.json"

    def load(self, key: str) -> CacheEntry | None:
        """Load and deserialize a cache entry for ``key`` if present."""
        path = self._entry_path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        timestamp = payload.get("cached_at")
        if not timestamp:
            return None
        try:
            cached_at = datetime.fromisoformat(timestamp)
        except ValueError:
            return None
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=UTC)
        return CacheEntry(data=payload.get("data"), cached_at=cached_at)

    def store(self, key: str, data: Any) -> None:
        """Persist ``data`` in the cache under ``key``."""
        path = self._entry_path(key)
        payload = {
            "cached_at": datetime.now(tz=UTC).isoformat(),
            "data": data,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def is_stale(self, entry: CacheEntry) -> bool:
        """Return ``True`` if ``entry`` exceeded the configured TTL."""
        return entry.age > self.ttl


class ApiError(RuntimeError):
    """Raised when an HTTP request fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Any | None = None,
    ) -> None:
        """Store HTTP error context for later reporting."""
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class ApiClient:
    """Thin wrapper around ``httpx.Client`` with Orcheo defaults."""

    def __init__(
        self,
        base_url: str,
        *,
        service_token: str | None,
        timeout: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Create a configured HTTP client for the Orcheo API."""
        headers = {
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        if service_token:
            headers["Authorization"] = f"Bearer {service_token}"
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers=headers,
            transport=transport,
        )

    def close(self) -> None:
        """Release the underlying HTTP resources."""
        self._client.close()

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Issue an HTTP request and raise :class:`ApiError` on failure."""
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            payload: Any | None
            try:
                payload = exc.response.json()
            except ValueError:
                payload = exc.response.text
            raise ApiError(
                f"Request failed with status {exc.response.status_code}",
                status_code=exc.response.status_code,
                payload=payload,
            ) from exc
        except httpx.HTTPError as exc:
            raise ApiError(f"HTTP error: {exc}") from exc

    def get_json(self, path: str, *, params: Mapping[str, Any] | None = None) -> Any:
        """Return the decoded JSON payload for a ``GET`` request."""
        response = self.request("GET", path, params=params)
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError("Unexpected response payload") from exc

    def post_json(self, path: str, *, json_payload: Any) -> Any:
        """Return the decoded JSON payload for a ``POST`` request."""
        response = self.request("POST", path, json=json_payload)
        try:
            return response.json()
        except ValueError:
            return None

    def delete(self, path: str) -> None:
        """Issue a ``DELETE`` request and ignore the response body."""
        self.request("DELETE", path)


@dataclass(slots=True)
class CliRuntime:
    """Container shared across command handlers."""

    settings: CliSettings
    console: Console
    cache: CacheStore
    offline: bool
    api: ApiClient | None = None

    def require_api(self) -> ApiClient:
        """Return the active API client or raise if offline."""
        if self.api is None:
            raise CliError(
                "This command requires network access; re-run without --offline",
            )
        return self.api


def build_console() -> Console:
    """Return a console configured for deterministic CLI output."""
    return Console(
        force_terminal=False,
        color_system=None,
        markup=False,
        highlight=False,
        width=100,
    )


def default_config_path() -> Path:
    """Return the default configuration file path for the CLI."""
    explicit = os.getenv(CONFIG_PATH_ENV_VAR)
    if explicit:
        return Path(explicit).expanduser()
    if os.name == "nt":
        base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "Orcheo" / "cli.toml"
    return Path.home() / ".config" / "orcheo" / "cli.toml"


def default_cache_path() -> Path:
    """Return the default cache directory used by the CLI."""
    explicit = os.getenv(CACHE_ENV_VAR)
    if explicit:
        return Path(explicit).expanduser()
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "Orcheo" / "Cache"
    return Path.home() / ".cache" / "orcheo"


def load_profiles(path: Path) -> Mapping[str, Mapping[str, Any]]:
    """Return the profile mapping defined in the CLI configuration file."""
    if not path.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError as exc:  # pragma: no cover - Python <3.11 safeguard
        raise CliError("Python 3.11+ is required for profile support") from exc
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise CliError(f"Invalid CLI configuration file: {path}") from exc
    profiles = payload.get("profiles", {})
    if not isinstance(profiles, Mapping):
        return {}
    return profiles


def resolve_settings(
    *,
    api_url: str | None,
    service_token: str | None,
    profile: str | None,
    timeout: float,
) -> CliSettings:
    """Resolve CLI settings from command line, environment, and profiles."""
    profile_name = profile or os.getenv(CONFIG_ENV_VAR)
    config_path = default_config_path()
    profiles = load_profiles(config_path)
    profile_data: Mapping[str, Any] = profiles.get(profile_name or "", {})

    env_api_url = os.getenv("ORCHEO_API_URL")
    env_token = os.getenv("ORCHEO_SERVICE_TOKEN")

    resolved_api_url = (
        api_url
        or (env_api_url.strip() if env_api_url else None)
        or (str(profile_data.get("api_url")).strip() if profile_data else None)
        or DEFAULT_API_URL
    )

    resolved_token = (
        service_token
        or (env_token.strip() if env_token else None)
        or (str(profile_data.get("service_token")).strip() if profile_data else None)
    )

    if not resolved_api_url:
        raise CliError("Unable to determine the Orcheo API URL")

    return CliSettings(
        api_url=resolved_api_url,
        service_token=resolved_token,
        profile=profile_name,
        timeout=timeout,
    )


def render_warning(console: Console, message: str) -> None:
    """Print a warning message to the console."""
    console.print(f"Warning: {message}")


def render_error(console: Console, message: str) -> None:
    """Print an error message to the console."""
    console.print(f"Error: {message}")
