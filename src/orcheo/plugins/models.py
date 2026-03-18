"""Plugin data models used by CLI and runtime integration."""

from __future__ import annotations
from dataclasses import dataclass, field


PLUGIN_API_VERSION = 1


@dataclass(slots=True)
class PluginManifest:
    """Normalized manifest assembled from package metadata and plugin manifest."""

    name: str
    version: str
    description: str
    author: str
    plugin_api_version: int
    orcheo_version: str
    exports: list[str]
    entry_points: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DesiredPluginRecord:
    """Desired plugin lifecycle state persisted in ``plugins.toml``."""

    name: str
    source: str
    enabled: bool = True
    install_source: str = "cli"
    status: str | None = None
    last_error: str | None = None


@dataclass(slots=True)
class LockedPluginRecord:
    """Resolved plugin install state persisted in ``plugin-lock.toml``."""

    name: str
    version: str
    plugin_api_version: int
    orcheo_version: str
    location: str
    wheel_sha256: str
    manifest_sha256: str
    exports: list[str]
    description: str = ""
    author: str = ""
    entry_points: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PluginStoragePaths:
    """Filesystem locations used by the plugin manager."""

    plugin_dir: str
    state_file: str
    lock_file: str
    install_dir: str
    wheels_dir: str
    manifests_dir: str
    cache_dir: str
    downloads_dir: str
    metadata_dir: str


@dataclass(slots=True)
class PluginImpactSummary:
    """Classification of how a plugin change should be applied."""

    change_type: str
    affected_component_kinds: list[str]
    affected_component_ids: list[str]
    activation_mode: str
    prompt_required: bool
    restart_required: bool = False


@dataclass(slots=True)
class DoctorCheck:
    """Single diagnostic emitted by ``orcheo plugin doctor``."""

    name: str
    severity: str
    ok: bool
    message: str


@dataclass(slots=True)
class DoctorReport:
    """Aggregate doctor result with convenience helpers."""

    checks: list[DoctorCheck]

    @property
    def has_errors(self) -> bool:
        """Return ``True`` when any diagnostic is an error."""
        return any(check.severity == "ERROR" and not check.ok for check in self.checks)


__all__ = [
    "PLUGIN_API_VERSION",
    "DesiredPluginRecord",
    "DoctorCheck",
    "DoctorReport",
    "LockedPluginRecord",
    "PluginImpactSummary",
    "PluginManifest",
    "PluginStoragePaths",
]
