"""Tests for configuration helpers."""

import pytest
from dynaconf import Dynaconf
from orcheo import config


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default settings fall back to SQLite and localhost server."""

    def _build_loader_without_dotenv() -> Dynaconf:
        return Dynaconf(
            envvar_prefix="ORCHEO",
            settings_files=[],
            load_dotenv=False,
            environments=False,
        )

    monkeypatch.setattr(config, "_build_loader", _build_loader_without_dotenv)

    monkeypatch.delenv("ORCHEO_CHECKPOINT_BACKEND", raising=False)
    monkeypatch.delenv("ORCHEO_SQLITE_PATH", raising=False)
    monkeypatch.delenv("ORCHEO_HOST", raising=False)
    monkeypatch.delenv("ORCHEO_PORT", raising=False)
    monkeypatch.delenv("ORCHEO_VAULT_BACKEND", raising=False)
    monkeypatch.delenv("ORCHEO_VAULT_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("ORCHEO_VAULT_LOCAL_PATH", raising=False)
    monkeypatch.delenv("ORCHEO_VAULT_AWS_REGION", raising=False)
    monkeypatch.delenv("ORCHEO_VAULT_AWS_KMS_KEY_ID", raising=False)
    monkeypatch.delenv("ORCHEO_VAULT_TOKEN_TTL_SECONDS", raising=False)

    settings = config.get_settings(refresh=True)

    assert settings.checkpoint_backend == "sqlite"
    assert settings.sqlite_path == "checkpoints.sqlite"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000
    assert settings.vault_backend == "inmemory"
    assert settings.vault_encryption_key is None
    assert settings.vault_local_path is None
    assert settings.vault_aws_region is None
    assert settings.vault_aws_kms_key_id is None
    assert settings.vault_token_ttl_seconds == 3600


def test_settings_invalid_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid persistence backend values raise a helpful error."""

    monkeypatch.setenv("ORCHEO_CHECKPOINT_BACKEND", "invalid")

    with pytest.raises(ValueError):
        config.get_settings(refresh=True)


def test_postgres_backend_requires_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Using Postgres without a DSN should fail fast."""

    monkeypatch.setenv("ORCHEO_CHECKPOINT_BACKEND", "postgres")
    monkeypatch.delenv("ORCHEO_POSTGRES_DSN", raising=False)

    with pytest.raises(ValueError):
        config.get_settings(refresh=True)


def test_normalize_backend_none() -> None:
    """Explicit `None` backend values should fall back to defaults."""

    source = Dynaconf(settings_files=[], load_dotenv=False, environments=False)
    source.set("CHECKPOINT_BACKEND", None)

    normalized = config._normalize_settings(source)

    assert normalized.checkpoint_backend == "sqlite"


def test_get_settings_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_settings refresh flag should reload cached values."""

    monkeypatch.setenv("ORCHEO_SQLITE_PATH", "initial.db")
    settings = config.get_settings(refresh=True)
    assert settings.sqlite_path == "initial.db"

    monkeypatch.setenv("ORCHEO_SQLITE_PATH", "updated.db")
    refreshed = config.get_settings(refresh=True)
    assert refreshed.sqlite_path == "updated.db"


def test_invalid_vault_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vault backend must match supported options."""

    monkeypatch.setenv("ORCHEO_VAULT_BACKEND", "unsupported")

    with pytest.raises(ValueError):
        config.get_settings(refresh=True)


def test_file_vault_requires_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Persistent vault backends require encryption settings."""

    monkeypatch.setenv("ORCHEO_VAULT_BACKEND", "file")
    monkeypatch.delenv("ORCHEO_VAULT_ENCRYPTION_KEY", raising=False)

    with pytest.raises(ValueError):
        config.get_settings(refresh=True)


def test_file_vault_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """File-based vault should populate default path when available."""

    monkeypatch.setenv("ORCHEO_VAULT_BACKEND", "file")
    monkeypatch.setenv("ORCHEO_VAULT_ENCRYPTION_KEY", "dummy-key")
    monkeypatch.delenv("ORCHEO_VAULT_LOCAL_PATH", raising=False)

    settings = config.get_settings(refresh=True)

    assert settings.vault_backend == "file"
    assert settings.vault_local_path == ".orcheo/vault.sqlite"
    assert settings.vault_encryption_key == "dummy-key"


def test_aws_vault_requires_region_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """AWS KMS-backed vaults need region and key identifiers."""

    monkeypatch.setenv("ORCHEO_VAULT_BACKEND", "aws_kms")
    monkeypatch.setenv("ORCHEO_VAULT_ENCRYPTION_KEY", "enc-key")
    monkeypatch.delenv("ORCHEO_VAULT_AWS_REGION", raising=False)
    monkeypatch.delenv("ORCHEO_VAULT_AWS_KMS_KEY_ID", raising=False)

    with pytest.raises(ValueError):
        config.get_settings(refresh=True)

    monkeypatch.setenv("ORCHEO_VAULT_AWS_REGION", "us-west-2")
    monkeypatch.setenv("ORCHEO_VAULT_AWS_KMS_KEY_ID", "kms-key-id")

    settings = config.get_settings(refresh=True)

    assert settings.vault_backend == "aws_kms"
    assert settings.vault_aws_region == "us-west-2"
    assert settings.vault_aws_kms_key_id == "kms-key-id"
    assert settings.vault_local_path is None


def test_vault_token_ttl_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Token TTL values must be positive integers."""

    monkeypatch.setenv("ORCHEO_VAULT_TOKEN_TTL_SECONDS", "-1")

    with pytest.raises(ValueError):
        config.get_settings(refresh=True)

    monkeypatch.setenv("ORCHEO_VAULT_TOKEN_TTL_SECONDS", "900")
    settings = config.get_settings(refresh=True)
    assert settings.vault_token_ttl_seconds == 900


def test_numeric_fields_accept_str_coercible_objects() -> None:
    """Port and vault TTL should coerce objects that stringify to integers."""

    class Intish:
        def __init__(self, value: int) -> None:
            self._value = value

        def __str__(self) -> str:
            return str(self._value)

    source = Dynaconf(settings_files=[], load_dotenv=False, environments=False)
    source.set("PORT", Intish(4711))
    source.set("VAULT_TOKEN_TTL_SECONDS", Intish(1234))

    normalized = config._normalize_settings(source)

    assert normalized.port == 4711
    assert normalized.vault_token_ttl_seconds == 1234
