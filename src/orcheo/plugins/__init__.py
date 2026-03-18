"""Public plugin subsystem exports."""

from orcheo.plugins.api import PluginAPI
from orcheo.plugins.loader import (
    PluginLoadReport,
    PluginLoadResult,
    ensure_plugins_loaded,
    invalidate_plugin_loader,
    load_enabled_plugins,
    reset_plugin_loader_for_tests,
)
from orcheo.plugins.manager import PLUGIN_ENTRYPOINT_GROUP, PluginError, PluginManager
from orcheo.plugins.models import (
    PLUGIN_API_VERSION,
    DesiredPluginRecord,
    DoctorCheck,
    DoctorReport,
    LockedPluginRecord,
    PluginImpactSummary,
    PluginManifest,
    PluginStoragePaths,
)
from orcheo.plugins.paths import build_storage_paths, get_cache_root, get_plugin_dir
from orcheo.plugins.state import (
    load_desired_state,
    load_lock_state,
    save_desired_state,
    save_lock_state,
)


__all__ = [
    "PLUGIN_API_VERSION",
    "PLUGIN_ENTRYPOINT_GROUP",
    "PluginAPI",
    "DesiredPluginRecord",
    "DoctorCheck",
    "DoctorReport",
    "LockedPluginRecord",
    "PluginError",
    "PluginImpactSummary",
    "PluginLoadReport",
    "PluginLoadResult",
    "PluginManager",
    "PluginManifest",
    "PluginStoragePaths",
    "build_storage_paths",
    "ensure_plugins_loaded",
    "get_cache_root",
    "get_plugin_dir",
    "invalidate_plugin_loader",
    "load_enabled_plugins",
    "load_desired_state",
    "load_lock_state",
    "reset_plugin_loader_for_tests",
    "save_desired_state",
    "save_lock_state",
]
