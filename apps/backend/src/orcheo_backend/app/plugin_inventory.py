"""Helpers for inspecting plugin availability in the current backend process."""

from __future__ import annotations
from collections.abc import Iterable
from typing import Any
from orcheo.plugins import PluginManager, load_enabled_plugins


def list_runtime_plugins() -> list[dict[str, Any]]:
    """Return plugin inventory plus current-process load status."""
    rows = PluginManager().list_plugins()
    report = load_enabled_plugins(force=False)
    results = {result.name: result for result in report.results}
    plugins: list[dict[str, Any]] = []
    for row in rows:
        name = str(row["name"])
        load_result = results.get(name)
        plugins.append(
            {
                "name": name,
                "enabled": bool(row["enabled"]),
                "status": str(row["status"]),
                "version": str(row["version"]),
                "exports": [str(item) for item in row["exports"]],
                "loaded": bool(load_result.loaded)
                if load_result is not None
                else False,
                "load_error": load_result.error if load_result is not None else None,
            }
        )
    return plugins


def missing_required_plugins(required_plugins: Iterable[str]) -> list[str]:
    """Return required plugin names unavailable in the current backend process."""
    required = sorted(
        {str(name).strip() for name in required_plugins if str(name).strip()}
    )
    if not required:
        return []
    inventory = {plugin["name"]: plugin for plugin in list_runtime_plugins()}
    missing: list[str] = []
    for name in required:
        plugin = inventory.get(name)
        if plugin is None or not plugin["enabled"] or not plugin["loaded"]:
            missing.append(name)
    return missing


__all__ = ["list_runtime_plugins", "missing_required_plugins"]
