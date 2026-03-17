"""Persistence helpers for plugin desired and lock state."""

from __future__ import annotations
import os
import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Any
from orcheo.plugins.models import DesiredPluginRecord, LockedPluginRecord


def _format_toml_value(value: Any) -> str:
    """Return a TOML literal for a small subset of value types."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        inner = ", ".join(_format_toml_value(item) for item in value)
        return f"[{inner}]"
    msg = f"Unsupported TOML value: {type(value)!r}"
    raise TypeError(msg)


def _atomic_write(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    os.replace(temp_path, path)


def _dump_records(records: list[dict[str, Any]]) -> str:
    """Serialize plugin records into the project TOML shape."""
    if not records:
        return ""
    lines: list[str] = []
    for record in records:
        lines.append("[[plugin]]")
        for key, value in record.items():
            if value is None:
                continue
            lines.append(f"{key} = {_format_toml_value(value)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def load_desired_state(path: Path) -> list[DesiredPluginRecord]:
    """Load desired plugin state from ``plugins.toml``."""
    if not path.exists():
        return []
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    return [
        DesiredPluginRecord(
            name=str(item["name"]),
            source=str(item["source"]),
            enabled=bool(item.get("enabled", True)),
            install_source=str(item.get("install_source", "cli")),
            status=str(item["status"]) if item.get("status") is not None else None,
            last_error=str(item["last_error"])
            if item.get("last_error") is not None
            else None,
        )
        for item in payload.get("plugin", [])
        if isinstance(item, dict) and item.get("name") and item.get("source")
    ]


def save_desired_state(path: Path, records: list[DesiredPluginRecord]) -> None:
    """Persist desired plugin state to ``plugins.toml``."""
    normalized = sorted(records, key=lambda item: item.name.lower())
    _atomic_write(path, _dump_records([asdict(record) for record in normalized]))


def load_lock_state(path: Path) -> list[LockedPluginRecord]:
    """Load resolved plugin state from ``plugin-lock.toml``."""
    if not path.exists():
        return []
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    records: list[LockedPluginRecord] = []
    for item in payload.get("plugin", []):
        if not isinstance(item, dict):
            continue
        if not item.get("name") or not item.get("version"):
            continue
        records.append(
            LockedPluginRecord(
                name=str(item["name"]),
                version=str(item["version"]),
                plugin_api_version=int(item.get("plugin_api_version", 0)),
                orcheo_version=str(item.get("orcheo_version", "")),
                location=str(item.get("location", "")),
                wheel_sha256=str(item.get("wheel_sha256", "")),
                manifest_sha256=str(item.get("manifest_sha256", "")),
                exports=[
                    str(export_name)
                    for export_name in item.get("exports", [])
                    if isinstance(export_name, str)
                ],
                description=str(item.get("description", "")),
                author=str(item.get("author", "")),
                entry_points=[
                    str(entry_name)
                    for entry_name in item.get("entry_points", [])
                    if isinstance(entry_name, str)
                ],
            )
        )
    return records


def save_lock_state(path: Path, records: list[LockedPluginRecord]) -> None:
    """Persist resolved plugin state to ``plugin-lock.toml``."""
    normalized = sorted(records, key=lambda item: item.name.lower())
    _atomic_write(path, _dump_records([asdict(record) for record in normalized]))


__all__ = [
    "load_desired_state",
    "load_lock_state",
    "save_desired_state",
    "save_lock_state",
]
