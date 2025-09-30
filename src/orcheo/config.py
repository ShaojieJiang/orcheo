"""Runtime configuration helpers for Orcheo."""

from __future__ import annotations
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, cast


CheckpointBackend = Literal["sqlite", "postgres"]


@dataclass(frozen=True, slots=True)
class PersistenceSettings:
    """Settings that describe how workflow checkpoints are stored."""

    backend: CheckpointBackend = "sqlite"
    sqlite_path: str = "checkpoints.sqlite"
    postgres_dsn: str | None = None

    @classmethod
    def from_env(cls) -> PersistenceSettings:
        """Build persistence settings using environment variables."""
        backend = os.getenv("ORCHEO_CHECKPOINT_BACKEND", "sqlite").lower()
        if backend not in {"sqlite", "postgres"}:
            msg = "ORCHEO_CHECKPOINT_BACKEND must be either 'sqlite' or 'postgres'."
            raise ValueError(msg)

        sqlite_path = os.getenv("ORCHEO_SQLITE_PATH", "checkpoints.sqlite")
        postgres_dsn = os.getenv("ORCHEO_POSTGRES_DSN")

        if backend == "postgres" and not postgres_dsn:
            msg = "ORCHEO_POSTGRES_DSN must be set when using the postgres backend."
            raise ValueError(msg)

        backend_value = cast(CheckpointBackend, backend)
        return cls(
            backend=backend_value,
            sqlite_path=sqlite_path,
            postgres_dsn=postgres_dsn,
        )


@dataclass(frozen=True, slots=True)
class Settings:
    """Aggregated application settings."""

    persistence: PersistenceSettings
    host: str = "0.0.0.0"
    port: int = 8000

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings by reading from the environment."""
        persistence = PersistenceSettings.from_env()
        host = os.getenv("ORCHEO_HOST", "0.0.0.0")
        port = int(os.getenv("ORCHEO_PORT", "8000"))

        return cls(persistence=persistence, host=host, port=port)


@lru_cache(maxsize=1)
def _load_settings() -> Settings:
    """Load settings once and cache the result."""
    return Settings.from_env()


def get_settings(*, refresh: bool = False) -> Settings:
    """Return the cached settings, reloading them if requested."""
    if refresh:
        _load_settings.cache_clear()
    return _load_settings()
