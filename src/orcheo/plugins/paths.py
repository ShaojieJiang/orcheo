"""Filesystem path helpers for the plugin subsystem."""

from __future__ import annotations
import os
from pathlib import Path
from orcheo.plugins.models import PluginStoragePaths


PLUGIN_DIR_ENV = "ORCHEO_PLUGIN_DIR"
CACHE_DIR_ENV = "ORCHEO_CACHE_DIR"


def get_plugin_dir() -> Path:
    """Return the plugin runtime directory."""
    override = os.getenv(PLUGIN_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".orcheo" / "plugins"


def get_cache_root() -> Path:
    """Return the Orcheo cache root."""
    override = os.getenv(CACHE_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "orcheo"


def build_storage_paths() -> PluginStoragePaths:
    """Return the default plugin storage layout."""
    plugin_dir = get_plugin_dir()
    cache_root = get_cache_root()
    cache_dir = cache_root / "plugins"
    return PluginStoragePaths(
        plugin_dir=str(plugin_dir),
        state_file=str(plugin_dir / "plugins.toml"),
        lock_file=str(plugin_dir / "plugin-lock.toml"),
        install_dir=str(plugin_dir / "venv"),
        wheels_dir=str(plugin_dir / "wheels"),
        manifests_dir=str(plugin_dir / "manifests"),
        cache_dir=str(cache_dir),
        downloads_dir=str(cache_dir / "downloads"),
        metadata_dir=str(cache_dir / "metadata"),
    )


__all__ = [
    "CACHE_DIR_ENV",
    "PLUGIN_DIR_ENV",
    "build_storage_paths",
    "get_cache_root",
    "get_plugin_dir",
]
