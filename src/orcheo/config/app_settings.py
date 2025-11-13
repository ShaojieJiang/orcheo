"""Application-level configuration models."""

from __future__ import annotations
from typing import cast
from pydantic import BaseModel, Field, field_validator, model_validator
from orcheo.config.chatkit_rate_limit_settings import ChatKitRateLimitSettings
from orcheo.config.defaults import _DEFAULTS
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
    tracing_exporter: str = Field(default=cast(str, _DEFAULTS["TRACING_EXPORTER"]))
    tracing_endpoint: str | None = None
    tracing_service_name: str = Field(
        default=cast(str, _DEFAULTS["TRACING_SERVICE_NAME"])
    )
    tracing_sample_ratio: float = Field(
        default=cast(float, _DEFAULTS["TRACING_SAMPLE_RATIO"]),
        ge=0.0,
        le=1.0,
    )
    tracing_insecure: bool = Field(default=cast(bool, _DEFAULTS["TRACING_INSECURE"]))
    tracing_high_token_threshold: int = Field(
        default=cast(int, _DEFAULTS["TRACING_HIGH_TOKEN_THRESHOLD"]),
        ge=1,
    )
    tracing_preview_max_length: int = Field(
        default=cast(int, _DEFAULTS["TRACING_PREVIEW_MAX_LENGTH"]),
        ge=16,
    )

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

    @field_validator("tracing_exporter", mode="before")
    @classmethod
    def _coerce_tracing_exporter(cls, value: object) -> str:
        candidate_source = value if value is not None else _DEFAULTS["TRACING_EXPORTER"]
        candidate = str(candidate_source).lower()
        allowed = {"none", "otlp", "console"}
        if candidate not in allowed:
            msg = "ORCHEO_TRACING_EXPORTER must be one of 'none', 'otlp', or 'console'."
            raise ValueError(msg)
        return candidate

    @field_validator("tracing_endpoint", mode="before")
    @classmethod
    def _coerce_tracing_endpoint(cls, value: object) -> str | None:
        if value is None:
            return None
        return str(value)

    @field_validator("tracing_service_name", mode="before")
    @classmethod
    def _coerce_tracing_service_name(cls, value: object) -> str:
        candidate = value if value is not None else _DEFAULTS["TRACING_SERVICE_NAME"]
        return str(candidate)

    @field_validator("tracing_sample_ratio", mode="before")
    @classmethod
    def _coerce_tracing_sample_ratio(cls, value: object) -> float:
        candidate_obj = (
            value if value is not None else _DEFAULTS["TRACING_SAMPLE_RATIO"]
        )
        try:
            if isinstance(candidate_obj, (int, float, str)):
                candidate = float(candidate_obj)
            else:
                candidate = float(str(candidate_obj))
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            msg = "ORCHEO_TRACING_SAMPLE_RATIO must be a float between 0 and 1."
            raise ValueError(msg) from exc
        if not 0.0 <= candidate <= 1.0:
            msg = "ORCHEO_TRACING_SAMPLE_RATIO must be between 0 and 1."
            raise ValueError(msg)
        return candidate

    @field_validator("tracing_insecure", mode="before")
    @classmethod
    def _coerce_tracing_insecure(cls, value: object) -> bool:
        candidate_obj = value if value is not None else _DEFAULTS["TRACING_INSECURE"]
        if isinstance(candidate_obj, bool):
            return candidate_obj
        if isinstance(candidate_obj, str):
            lowered = candidate_obj.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
        return bool(candidate_obj)

    @field_validator("tracing_high_token_threshold", mode="before")
    @classmethod
    def _coerce_tracing_high_token_threshold(cls, value: object) -> int:
        candidate_obj = (
            value if value is not None else _DEFAULTS["TRACING_HIGH_TOKEN_THRESHOLD"]
        )
        if isinstance(candidate_obj, bool):  # pragma: no cover - defensive
            return int(candidate_obj)
        if isinstance(candidate_obj, (int, float)):
            return int(candidate_obj)
        try:
            return int(str(candidate_obj))
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            msg = "ORCHEO_TRACING_HIGH_TOKEN_THRESHOLD must be a positive integer."
            raise ValueError(msg) from exc

    @field_validator("tracing_preview_max_length", mode="before")
    @classmethod
    def _coerce_tracing_preview_max_length(cls, value: object) -> int:
        candidate_obj = (
            value if value is not None else _DEFAULTS["TRACING_PREVIEW_MAX_LENGTH"]
        )
        if isinstance(candidate_obj, bool):  # pragma: no cover - defensive
            return int(candidate_obj)
        if isinstance(candidate_obj, (int, float)):
            return int(candidate_obj)
        try:
            return int(str(candidate_obj))
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            msg = "ORCHEO_TRACING_PREVIEW_MAX_LENGTH must be a positive integer."
            raise ValueError(msg) from exc

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
        if not self.tracing_exporter:
            self.tracing_exporter = cast(str, _DEFAULTS["TRACING_EXPORTER"])
        if not self.tracing_service_name:
            self.tracing_service_name = cast(str, _DEFAULTS["TRACING_SERVICE_NAME"])
        if self.tracing_high_token_threshold <= 0:
            self.tracing_high_token_threshold = cast(
                int, _DEFAULTS["TRACING_HIGH_TOKEN_THRESHOLD"]
            )
        if self.tracing_preview_max_length <= 0:
            self.tracing_preview_max_length = cast(
                int, _DEFAULTS["TRACING_PREVIEW_MAX_LENGTH"]
            )
        return self


__all__ = ["AppSettings"]
