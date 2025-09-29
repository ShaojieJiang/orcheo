"""Tests for configuration helpers."""

import pytest

from orcheo import config


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default settings fall back to SQLite and localhost server."""

    monkeypatch.delenv("ORCHEO_CHECKPOINT_BACKEND", raising=False)
    monkeypatch.delenv("ORCHEO_SQLITE_PATH", raising=False)
    monkeypatch.delenv("ORCHEO_HOST", raising=False)
    monkeypatch.delenv("ORCHEO_PORT", raising=False)

    settings = config.Settings.from_env()

    assert settings.persistence.backend == "sqlite"
    assert settings.persistence.sqlite_path == "checkpoints.sqlite"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000


def test_settings_invalid_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid persistence backend values raise a helpful error."""

    monkeypatch.setenv("ORCHEO_CHECKPOINT_BACKEND", "invalid")

    with pytest.raises(ValueError):
        config.Settings.from_env()


def test_postgres_backend_requires_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Using Postgres without a DSN should fail fast."""

    monkeypatch.setenv("ORCHEO_CHECKPOINT_BACKEND", "postgres")
    monkeypatch.delenv("ORCHEO_POSTGRES_DSN", raising=False)

    with pytest.raises(ValueError):
        config.Settings.from_env()


def test_get_settings_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_settings refresh flag should reload cached values."""

    monkeypatch.setenv("ORCHEO_SQLITE_PATH", "initial.db")
    settings = config.get_settings(refresh=True)
    assert settings.persistence.sqlite_path == "initial.db"

    monkeypatch.setenv("ORCHEO_SQLITE_PATH", "updated.db")
    refreshed = config.get_settings(refresh=True)
    assert refreshed.persistence.sqlite_path == "updated.db"

