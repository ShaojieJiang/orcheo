"""Plugin lifecycle service operations."""

from __future__ import annotations
from collections.abc import Callable
from typing import Any
from orcheo.plugins import PluginManager, invalidate_plugin_loader


def list_plugins_data() -> list[dict[str, Any]]:
    """Return the current plugin inventory."""
    return PluginManager().list_plugins()


def show_plugin_data(name: str) -> dict[str, Any]:
    """Return details for ``name``."""
    return PluginManager().show_plugin(name)


def install_plugin_data(
    ref: str,
    *,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Install a plugin from ``ref``."""
    result = PluginManager().install(ref, progress=progress)
    invalidate_plugin_loader()
    return result


def update_plugin_data(
    name: str,
    *,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Update a single plugin using its stored source ref."""
    result = PluginManager().update(name, progress=progress)
    invalidate_plugin_loader()
    return result


def preview_update_plugin_data(name: str) -> dict[str, Any]:
    """Return update impact for a single plugin without mutating state."""
    impact = PluginManager().preview_update(name)
    return {"name": name, "impact": impact}


def update_all_plugins_data(
    *,
    progress: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    """Update all configured plugins."""
    result = PluginManager().update_all(progress=progress)
    invalidate_plugin_loader()
    return result


def preview_update_all_plugins_data() -> list[dict[str, Any]]:
    """Return update impact for all plugins without mutating state."""
    return PluginManager().preview_update_all()


def uninstall_plugin_data(name: str) -> dict[str, Any]:
    """Uninstall ``name`` and return the computed impact."""
    impact = PluginManager().uninstall(name)
    invalidate_plugin_loader()
    return {"name": name, "impact": impact}


def preview_uninstall_plugin_data(name: str) -> dict[str, Any]:
    """Return uninstall impact for ``name`` without mutating state."""
    impact = PluginManager().preview_uninstall(name)
    return {"name": name, "impact": impact}


def enable_plugin_data(name: str) -> dict[str, Any]:
    """Enable ``name`` and return the computed impact."""
    impact = PluginManager().set_enabled(name, enabled=True)
    invalidate_plugin_loader()
    return {"name": name, "impact": impact}


def preview_enable_plugin_data(name: str) -> dict[str, Any]:
    """Return enable impact for ``name`` without mutating state."""
    impact = PluginManager().preview_set_enabled(name, enabled=True)
    return {"name": name, "impact": impact}


def disable_plugin_data(name: str) -> dict[str, Any]:
    """Disable ``name`` and return the computed impact."""
    impact = PluginManager().set_enabled(name, enabled=False)
    invalidate_plugin_loader()
    return {"name": name, "impact": impact}


def preview_disable_plugin_data(name: str) -> dict[str, Any]:
    """Return disable impact for ``name`` without mutating state."""
    impact = PluginManager().preview_set_enabled(name, enabled=False)
    return {"name": name, "impact": impact}


def doctor_plugins_data() -> dict[str, Any]:
    """Return the doctor report as a serializable dictionary."""
    report = PluginManager().doctor()
    return {
        "checks": [
            {
                "name": check.name,
                "severity": check.severity,
                "ok": check.ok,
                "message": check.message,
            }
            for check in report.checks
        ],
        "has_errors": report.has_errors,
    }


__all__ = [
    "disable_plugin_data",
    "doctor_plugins_data",
    "enable_plugin_data",
    "install_plugin_data",
    "list_plugins_data",
    "preview_disable_plugin_data",
    "preview_enable_plugin_data",
    "preview_uninstall_plugin_data",
    "preview_update_all_plugins_data",
    "preview_update_plugin_data",
    "show_plugin_data",
    "uninstall_plugin_data",
    "update_all_plugins_data",
    "update_plugin_data",
]
