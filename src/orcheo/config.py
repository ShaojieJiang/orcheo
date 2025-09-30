"""Runtime configuration helpers for Orcheo."""

from __future__ import annotations
from functools import lru_cache
from typing import Literal, cast
from dynaconf import Dynaconf


CheckpointBackend = Literal["sqlite", "postgres"]

_DEFAULTS: dict[str, object] = {
    "CHECKPOINT_BACKEND": "sqlite",
    "SQLITE_PATH": "checkpoints.sqlite",
    "POSTGRES_DSN": None,
    "HOST": "0.0.0.0",
    "PORT": 8000,
}


def _build_loader() -> Dynaconf:
    """Create a Dynaconf loader wired to environment variables only."""
    return Dynaconf(
        envvar_prefix="ORCHEO",
        settings_files=[],  # No config files, env vars only
        load_dotenv=True,
        environments=False,
    )


def _normalize_settings(source: Dynaconf) -> Dynaconf:
    """Validate and fill defaults on the raw Dynaconf settings."""
    backend_raw = source.get("CHECKPOINT_BACKEND", _DEFAULTS["CHECKPOINT_BACKEND"])
    if backend_raw is None:
        backend = str(_DEFAULTS["CHECKPOINT_BACKEND"]).lower()
    else:
        backend = str(backend_raw).lower()
    if backend not in {"sqlite", "postgres"}:
        msg = "ORCHEO_CHECKPOINT_BACKEND must be either 'sqlite' or 'postgres'."
        raise ValueError(msg)

    normalized = Dynaconf(
        envvar_prefix="ORCHEO",
        settings_files=[],
        load_dotenv=False,
        environments=False,
    )
    normalized.set("CHECKPOINT_BACKEND", cast(CheckpointBackend, backend))

    sqlite_path = source.get("SQLITE_PATH") or _DEFAULTS["SQLITE_PATH"]
    normalized.set("SQLITE_PATH", str(sqlite_path))

    host = source.get("HOST") or _DEFAULTS["HOST"]
    normalized.set("HOST", str(host))

    port_raw = source.get("PORT", _DEFAULTS["PORT"])
    try:
        port = int(port_raw)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError("ORCHEO_PORT must be an integer.") from exc
    normalized.set("PORT", port)

    if backend == "postgres":
        dsn = source.get("POSTGRES_DSN")
        if not dsn:
            msg = "ORCHEO_POSTGRES_DSN must be set when using the postgres backend."
            raise ValueError(msg)
        normalized.set("POSTGRES_DSN", str(dsn))
    else:
        normalized.set("POSTGRES_DSN", None)

    return normalized


@lru_cache(maxsize=1)
def _load_settings() -> Dynaconf:
    """Load settings once and cache the normalized Dynaconf instance."""
    return _normalize_settings(_build_loader())


def get_settings(*, refresh: bool = False) -> Dynaconf:
    """Return the cached Dynaconf settings, reloading them if requested."""
    if refresh:
        _load_settings.cache_clear()
    return _load_settings()
