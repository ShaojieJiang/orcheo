"""Helpers for reading and caching Dynaconf settings."""

from __future__ import annotations
from functools import lru_cache
from dynaconf import Dynaconf
from pydantic import ValidationError
from orcheo.config.app_settings import AppSettings
from orcheo.config.defaults import _DEFAULTS
from orcheo.config.vault_settings import VaultSettings


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
    try:
        settings = AppSettings(
            checkpoint_backend=source.get("CHECKPOINT_BACKEND"),
            sqlite_path=source.get("SQLITE_PATH", _DEFAULTS["SQLITE_PATH"]),
            repository_backend=source.get(
                "REPOSITORY_BACKEND", _DEFAULTS["REPOSITORY_BACKEND"]
            ),
            repository_sqlite_path=source.get(
                "REPOSITORY_SQLITE_PATH", _DEFAULTS["REPOSITORY_SQLITE_PATH"]
            ),
            chatkit_sqlite_path=source.get(
                "CHATKIT_SQLITE_PATH", _DEFAULTS["CHATKIT_SQLITE_PATH"]
            ),
            chatkit_storage_path=source.get(
                "CHATKIT_STORAGE_PATH", _DEFAULTS["CHATKIT_STORAGE_PATH"]
            ),
            chatkit_retention_days=source.get(
                "CHATKIT_RETENTION_DAYS", _DEFAULTS["CHATKIT_RETENTION_DAYS"]
            ),
            postgres_dsn=source.get("POSTGRES_DSN"),
            host=source.get("HOST", _DEFAULTS["HOST"]),
            port=source.get("PORT", _DEFAULTS["PORT"]),
            vault=VaultSettings(
                backend=source.get("VAULT_BACKEND", _DEFAULTS["VAULT_BACKEND"]),
                encryption_key=source.get("VAULT_ENCRYPTION_KEY"),
                local_path=source.get(
                    "VAULT_LOCAL_PATH", _DEFAULTS["VAULT_LOCAL_PATH"]
                ),
                aws_region=source.get("VAULT_AWS_REGION"),
                aws_kms_key_id=source.get("VAULT_AWS_KMS_KEY_ID"),
                token_ttl_seconds=source.get(
                    "VAULT_TOKEN_TTL_SECONDS", _DEFAULTS["VAULT_TOKEN_TTL_SECONDS"]
                ),
            ),
        )
    except ValidationError as exc:  # pragma: no cover - defensive
        raise ValueError(str(exc)) from exc

    normalized = Dynaconf(
        envvar_prefix="ORCHEO",
        settings_files=[],
        load_dotenv=False,
        environments=False,
    )
    normalized.set("CHECKPOINT_BACKEND", settings.checkpoint_backend)
    normalized.set("SQLITE_PATH", settings.sqlite_path)
    normalized.set("REPOSITORY_BACKEND", settings.repository_backend)
    normalized.set("REPOSITORY_SQLITE_PATH", settings.repository_sqlite_path)
    normalized.set("CHATKIT_SQLITE_PATH", settings.chatkit_sqlite_path)
    normalized.set("CHATKIT_STORAGE_PATH", settings.chatkit_storage_path)
    normalized.set("CHATKIT_RETENTION_DAYS", settings.chatkit_retention_days)
    normalized.set("POSTGRES_DSN", settings.postgres_dsn)
    normalized.set("HOST", settings.host)
    normalized.set("PORT", settings.port)
    normalized.set("VAULT_BACKEND", settings.vault.backend)
    normalized.set("VAULT_ENCRYPTION_KEY", settings.vault.encryption_key)
    normalized.set("VAULT_LOCAL_PATH", settings.vault.local_path)
    normalized.set("VAULT_AWS_REGION", settings.vault.aws_region)
    normalized.set("VAULT_AWS_KMS_KEY_ID", settings.vault.aws_kms_key_id)
    normalized.set("VAULT_TOKEN_TTL_SECONDS", settings.vault.token_ttl_seconds)

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


__all__ = ["_build_loader", "_normalize_settings", "_load_settings", "get_settings"]
