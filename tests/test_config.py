"""Tests for configuration helpers."""

import pytest
from dynaconf import Dynaconf
from orcheo import config


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default settings fall back to SQLite and localhost server."""

    monkeypatch.delenv("ORCHEO_CHECKPOINT_BACKEND", raising=False)
    monkeypatch.delenv("ORCHEO_SQLITE_PATH", raising=False)
    monkeypatch.delenv("ORCHEO_HOST", raising=False)
    monkeypatch.delenv("ORCHEO_PORT", raising=False)

    settings = config.get_settings(refresh=True)

    assert settings.checkpoint_backend == "sqlite"
    assert settings.sqlite_path == "checkpoints.sqlite"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000


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
