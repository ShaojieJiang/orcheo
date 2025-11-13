"""Application-level configuration models."""

from __future__ import annotations
from typing import cast
from pydantic import BaseModel, Field, field_validator, model_validator
from orcheo.config.chatkit_rate_limit_settings import ChatKitRateLimitSettings
from orcheo.config.defaults import _DEFAULTS
from orcheo.config.telemetry_settings import TelemetrySettings
from orcheo.config.types import CheckpointBackend, RepositoryBackend
from orcheo.config.vault_settings import VaultSettings


class AppSettings(BaseModel):
    """Validated application runtime settings."""

    checkpoint_backend: CheckpointBackend = Field(
        default=cast(CheckpointBackend, _DEFAULTS["CHECKPOINT_BACKEND"])
    )
    sqlite_path: str = Field(default=cast(str, _DEFAULTS["SQLITE_PATH"]))
    repository_backend: RepositoryBackend = Field(
        default=cast(RepositoryBackend, _DEFAULTS["REPOSITORY_BACKEND"])
    )
    repository_sqlite_path: str = Field(
        default=cast(str, _DEFAULTS["REPOSITORY_SQLITE_PATH"])
    )
    chatkit_sqlite_path: str = Field(
        default=cast(str, _DEFAULTS["CHATKIT_SQLITE_PATH"])
    )
    chatkit_storage_path: str = Field(
        default=cast(str, _DEFAULTS["CHATKIT_STORAGE_PATH"])
    )
    chatkit_retention_days: int = Field(
        default=cast(int, _DEFAULTS["CHATKIT_RETENTION_DAYS"]), gt=0
    )
    chatkit_rate_limits: ChatKitRateLimitSettings = Field(
        default_factory=ChatKitRateLimitSettings
    )
    postgres_dsn: str | None = None
    host: str = Field(default=cast(str, _DEFAULTS["HOST"]))
    port: int = Field(default=cast(int, _DEFAULTS["PORT"]))
    vault: VaultSettings = Field(default_factory=VaultSettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)

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

    @field_validator("repository_backend", mode="before")
    @classmethod
    def _coerce_repository_backend(cls, value: object) -> RepositoryBackend:
        candidate = (
            cast(str, value).lower()
            if value is not None
            else cast(str, _DEFAULTS["REPOSITORY_BACKEND"])
        )
        if candidate not in {"inmemory", "sqlite"}:
            msg = "ORCHEO_REPOSITORY_BACKEND must be either 'inmemory' or 'sqlite'."
            raise ValueError(msg)
        return cast(RepositoryBackend, candidate)

    @field_validator("sqlite_path", "host", mode="before")
    @classmethod
    def _coerce_str(cls, value: object) -> str:
        return str(value) if value is not None else ""

    @field_validator("repository_sqlite_path", mode="before")
    @classmethod
    def _coerce_repo_sqlite_path(cls, value: object) -> str:
        return str(value) if value is not None else ""

    @field_validator("chatkit_sqlite_path", mode="before")
    @classmethod
    def _coerce_chatkit_sqlite_path(cls, value: object) -> str:
        return str(value) if value is not None else ""

    @field_validator("chatkit_storage_path", mode="before")
    @classmethod
    def _coerce_chatkit_storage_path(cls, value: object) -> str:
        return str(value) if value is not None else ""

    @field_validator("chatkit_retention_days", mode="before")
    @classmethod
    def _coerce_chatkit_retention(cls, value: object) -> int:
        candidate_obj = (
            value if value is not None else _DEFAULTS["CHATKIT_RETENTION_DAYS"]
        )
        if isinstance(candidate_obj, int):
            return candidate_obj
        try:
            return int(str(candidate_obj))
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            msg = "ORCHEO_CHATKIT_RETENTION_DAYS must be an integer."
            raise ValueError(msg) from exc

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
        self.repository_sqlite_path = self.repository_sqlite_path or cast(
            str, _DEFAULTS["REPOSITORY_SQLITE_PATH"]
        )
        self.chatkit_sqlite_path = self.chatkit_sqlite_path or cast(
            str, _DEFAULTS["CHATKIT_SQLITE_PATH"]
        )
        self.chatkit_storage_path = self.chatkit_storage_path or cast(
            str, _DEFAULTS["CHATKIT_STORAGE_PATH"]
        )
        if self.chatkit_retention_days <= 0:  # pragma: no cover - defensive
            self.chatkit_retention_days = cast(int, _DEFAULTS["CHATKIT_RETENTION_DAYS"])
        if not isinstance(self.chatkit_rate_limits, ChatKitRateLimitSettings):
            self.chatkit_rate_limits = ChatKitRateLimitSettings()
        self.host = self.host or cast(str, _DEFAULTS["HOST"])
        return self


__all__ = ["AppSettings"]
