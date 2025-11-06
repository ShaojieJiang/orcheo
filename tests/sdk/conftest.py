"""Shared fixtures for CLI tests."""

from __future__ import annotations
from pathlib import Path
import pytest
from typer.testing import CliRunner


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def env(tmp_path: Path) -> dict[str, str]:
    config_dir = tmp_path / "config"
    cache_dir = tmp_path / "cache"
    config_dir.mkdir()
    cache_dir.mkdir()
    return {
        "ORCHEO_API_URL": "http://api.test",
        "ORCHEO_SERVICE_TOKEN": "token",
        "ORCHEO_CONFIG_DIR": str(config_dir),
        "ORCHEO_CACHE_DIR": str(cache_dir),
        "NO_COLOR": "1",
    }


@pytest.fixture()
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up mock environment variables for SDK tests."""
    monkeypatch.setenv("ORCHEO_API_URL", "http://api.test")
    monkeypatch.setenv("ORCHEO_SERVICE_TOKEN", "test-token")
