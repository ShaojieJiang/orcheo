"""Runtime configuration helpers for Orcheo."""

from __future__ import annotations
from functools import lru_cache
from typing import Literal, cast
from dynaconf import Dynaconf
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


CheckpointBackend = Literal["sqlite", "postgres"]
VaultBackend = Literal["inmemory", "file", "aws_kms"]

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


class VaultSettings(BaseModel):
    """Validated representation of secure storage configuration."""

    backend: VaultBackend = Field(
        default=cast(VaultBackend, _DEFAULTS["VAULT_BACKEND"])
    )
    encryption_key: str | None = None
    local_path: str | None = None
    aws_region: str | None = None
    aws_kms_key_id: str | None = None
    token_ttl_seconds: int = Field(
        default=cast(int, _DEFAULTS["VAULT_TOKEN_TTL_SECONDS"]), gt=0
    )

    @field_validator("backend", mode="before")
    @classmethod
    def _coerce_backend(cls, value: object) -> VaultBackend:
        candidate = (
            cast(str, value).lower()
            if value is not None
            else cast(str, _DEFAULTS["VAULT_BACKEND"])
        )
        if candidate not in {"inmemory", "file", "aws_kms"}:
            msg = (
                "ORCHEO_VAULT_BACKEND must be one of 'inmemory', 'file', or 'aws_kms'."
            )
            raise ValueError(msg)
        return cast(VaultBackend, candidate)

    @field_validator("encryption_key", "local_path", "aws_region", "aws_kms_key_id")
    @classmethod
    def _coerce_optional_str(cls, value: object) -> str | None:
        return None if value is None else str(value)

    @field_validator("token_ttl_seconds", mode="before")
    @classmethod
    def _parse_token_ttl(cls, value: object) -> int:
        candidate_obj = (
            value if value is not None else _DEFAULTS["VAULT_TOKEN_TTL_SECONDS"]
        )
        candidate: int | str
        if isinstance(candidate_obj, int | str):
            candidate = candidate_obj
        else:
            candidate = str(candidate_obj)
        try:
            return int(candidate)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            msg = "ORCHEO_VAULT_TOKEN_TTL_SECONDS must be an integer."
            raise ValueError(msg) from exc

    @model_validator(mode="after")
    def _validate_backend_requirements(self) -> VaultSettings:
        if self.token_ttl_seconds <= 0:  # pragma: no cover - defensive
            msg = "ORCHEO_VAULT_TOKEN_TTL_SECONDS must be greater than zero."
            raise ValueError(msg)

        if self.backend != "inmemory" and not self.encryption_key:
            msg = (
                "ORCHEO_VAULT_ENCRYPTION_KEY must be set when using persistent "
                "vault backends."
            )
            raise ValueError(msg)

        if self.backend == "file":
            self.local_path = self.local_path or cast(
                str, _DEFAULTS["VAULT_LOCAL_PATH"]
            )
            self.aws_region = None
            self.aws_kms_key_id = None
        elif self.backend == "aws_kms":
            if not self.aws_region or not self.aws_kms_key_id:
                msg = (
                    "ORCHEO_VAULT_AWS_REGION and ORCHEO_VAULT_AWS_KMS_KEY_ID must be "
                    "set when using the aws_kms vault backend."
                )
                raise ValueError(msg)
            self.local_path = None
        else:  # inmemory
            self.local_path = None
            self.aws_region = None
            self.aws_kms_key_id = None

        return self


class AppSettings(BaseModel):
    """Validated application runtime settings."""

    checkpoint_backend: CheckpointBackend = Field(
        default=cast(CheckpointBackend, _DEFAULTS["CHECKPOINT_BACKEND"])
    )
    sqlite_path: str = Field(default=cast(str, _DEFAULTS["SQLITE_PATH"]))
    postgres_dsn: str | None = None
    host: str = Field(default=cast(str, _DEFAULTS["HOST"]))
    port: int = Field(default=cast(int, _DEFAULTS["PORT"]))
    vault: VaultSettings = Field(default_factory=VaultSettings)

    @field_validator("checkpoint_backend", mode="before")
    @classmethod
    def _coerce_checkpoint_backend(cls, value: object) -> CheckpointBackend:
        candidate = (
            cast(str, value).lower()
            if value is not None
            else cast(str, _DEFAULTS["CHECKPOINT_BACKEND"])
        )
        if candidate not in {"sqlite", "postgres"}:
            msg = "ORCHEO_CHECKPOINT_BACKEND must be either 'sqlite' or 'postgres'."
            raise ValueError(msg)
        return cast(CheckpointBackend, candidate)

    @field_validator("sqlite_path", "host", mode="before")
    @classmethod
    def _coerce_str(cls, value: object) -> str:
        return str(value) if value is not None else ""

    @field_validator("port", mode="before")
    @classmethod
    def _parse_port(cls, value: object) -> int:
        candidate_obj = value if value is not None else _DEFAULTS["PORT"]
        candidate: int | str
        if isinstance(candidate_obj, int | str):
            candidate = candidate_obj
        else:
            candidate = str(candidate_obj)
        try:
            return int(candidate)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ValueError("ORCHEO_PORT must be an integer.") from exc

    @model_validator(mode="after")
    def _validate_postgres_requirements(self) -> AppSettings:
        if self.checkpoint_backend == "postgres":
            if not self.postgres_dsn:
                msg = "ORCHEO_POSTGRES_DSN must be set when using the postgres backend."
                raise ValueError(msg)
            self.postgres_dsn = str(self.postgres_dsn)
        else:
            self.postgres_dsn = None

        self.sqlite_path = self.sqlite_path or cast(str, _DEFAULTS["SQLITE_PATH"])
        self.host = self.host or cast(str, _DEFAULTS["HOST"])
        return self


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
