"""Runtime configuration helpers for Orcheo."""

from __future__ import annotations
from functools import lru_cache
from typing import Literal, cast
from dynaconf import Dynaconf


CheckpointBackend = Literal["sqlite", "postgres"]
"""Supported checkpoint storage backend types."""

VaultBackend = Literal["inmemory", "file", "aws_kms"]
"""Supported credential vault backend types."""

_DEFAULTS: dict[str, object] = {
    "CHECKPOINT_BACKEND": "sqlite",
    "SQLITE_PATH": "checkpoints.sqlite",
    "POSTGRES_DSN": None,
    "HOST": "0.0.0.0",
    "PORT": 8000,
    "VAULT_BACKEND": "inmemory",
    "VAULT_ENCRYPTION_KEY": None,
    "VAULT_LOCAL_PATH": ".orcheo/vault.sqlite",
    "VAULT_AWS_REGION": None,
    "VAULT_AWS_KMS_KEY_ID": None,
    "VAULT_TOKEN_TTL_SECONDS": 3600,
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

    vault_backend_raw = source.get("VAULT_BACKEND", _DEFAULTS["VAULT_BACKEND"])
    vault_backend = str(vault_backend_raw).lower()
    if vault_backend not in {"inmemory", "file", "aws_kms"}:
        msg = (
            "ORCHEO_VAULT_BACKEND must be one of 'inmemory', 'file', or 'aws_kms'."
        )
        raise ValueError(msg)
    normalized.set("VAULT_BACKEND", cast(VaultBackend, vault_backend))

    encryption_key = source.get("VAULT_ENCRYPTION_KEY")
    if vault_backend != "inmemory" and not encryption_key:
        msg = (
            "ORCHEO_VAULT_ENCRYPTION_KEY must be set when using persistent vault backends."
        )
        raise ValueError(msg)
    normalized.set(
        "VAULT_ENCRYPTION_KEY",
        str(encryption_key) if encryption_key is not None else None,
    )

    token_ttl_raw = source.get(
        "VAULT_TOKEN_TTL_SECONDS", _DEFAULTS["VAULT_TOKEN_TTL_SECONDS"]
    )
    try:
        token_ttl = int(token_ttl_raw)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        msg = "ORCHEO_VAULT_TOKEN_TTL_SECONDS must be an integer."
        raise ValueError(msg) from exc
    if token_ttl <= 0:
        msg = "ORCHEO_VAULT_TOKEN_TTL_SECONDS must be greater than zero."
        raise ValueError(msg)
    normalized.set("VAULT_TOKEN_TTL_SECONDS", token_ttl)

    if vault_backend == "file":
        vault_path = source.get("VAULT_LOCAL_PATH") or _DEFAULTS["VAULT_LOCAL_PATH"]
        normalized.set("VAULT_LOCAL_PATH", str(vault_path))
        normalized.set("VAULT_AWS_REGION", None)
        normalized.set("VAULT_AWS_KMS_KEY_ID", None)
    elif vault_backend == "aws_kms":
        region = source.get("VAULT_AWS_REGION")
        key_id = source.get("VAULT_AWS_KMS_KEY_ID")
        if not region or not key_id:
            msg = (
                "ORCHEO_VAULT_AWS_REGION and ORCHEO_VAULT_AWS_KMS_KEY_ID must be set "
                "when using the aws_kms vault backend."
            )
            raise ValueError(msg)
        normalized.set("VAULT_AWS_REGION", str(region))
        normalized.set("VAULT_AWS_KMS_KEY_ID", str(key_id))
        normalized.set("VAULT_LOCAL_PATH", None)
    else:  # inmemory
        normalized.set("VAULT_LOCAL_PATH", None)
        normalized.set("VAULT_AWS_REGION", None)
        normalized.set("VAULT_AWS_KMS_KEY_ID", None)

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
