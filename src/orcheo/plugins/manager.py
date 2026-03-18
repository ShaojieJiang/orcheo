"""Transactional plugin installation and inspection helpers."""

from __future__ import annotations
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from packaging.utils import canonicalize_name
from orcheo.plugins.compatibility import (
    check_manifest_compatibility,
    classify_plugin_change,
    get_running_orcheo_version,
)
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
from orcheo.plugins.paths import build_storage_paths
from orcheo.plugins.state import (
    load_desired_state,
    load_lock_state,
    save_desired_state,
    save_lock_state,
)


PLUGIN_ENTRYPOINT_GROUP = "orcheo.plugins"


class PluginError(RuntimeError):
    """Raised when plugin lifecycle operations fail."""


def _run_command(
    command: list[str], *, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess and return its completed process object."""
    return subprocess.run(
        command,
        check=False,
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
    )


def _ensure_venv(path: Path) -> None:
    """Create a Python virtual environment at ``path``."""
    result = _run_command(["uv", "venv", str(path), "--python", sys.executable])
    if result.returncode != 0:
        raise PluginError(result.stderr.strip() or "Unable to create plugin venv.")


def _venv_python(path: Path) -> Path:
    """Return the Python executable inside a virtual environment."""
    return path / "bin" / "python"


def _site_packages(path: Path) -> Path:
    """Return the site-packages path for the plugin venv."""
    return (
        path
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest for ``path``."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest_payload(path: Path) -> dict[str, Any]:
    """Read plugin manifest payload from ``path``."""
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    if {"plugin_api_version", "orcheo_version", "exports"} <= payload.keys():
        return payload
    return payload.get("tool", {}).get("orcheo", {}).get("plugin", {})


@contextmanager
def _temporary_sys_path(path: Path) -> Iterator[None]:
    """Temporarily prepend a site-packages path to ``sys.path``."""
    sys.path.insert(0, str(path))
    try:
        yield
    finally:
        try:
            sys.path.remove(str(path))
        except ValueError:
            pass


def _find_manifest_file(distribution: importlib.metadata.Distribution) -> Path | None:
    """Locate ``orcheo_plugin.toml`` or an installed ``pyproject.toml``."""
    files = distribution.files or []
    for file in files:
        if file.name == "orcheo_plugin.toml":
            return Path(str(distribution.locate_file(file)))
    for file in files:
        if file.name == "pyproject.toml":
            return Path(str(distribution.locate_file(file)))
    return None


def _distribution_to_manifest(
    distribution: importlib.metadata.Distribution,
) -> tuple[PluginManifest, str]:
    """Return the normalized manifest and manifest hash for a distribution."""
    manifest_file = _find_manifest_file(distribution)
    if manifest_file is None or not manifest_file.exists():
        msg = f"Plugin {distribution.metadata['Name']} is missing orcheo_plugin.toml."
        raise PluginError(msg)
    payload = _load_manifest_payload(manifest_file)
    if not payload:
        msg = f"Plugin {distribution.metadata['Name']} has an empty plugin manifest."
        raise PluginError(msg)
    entry_points = [
        f"{entry.name}={entry.value}"
        for entry in distribution.entry_points
        if entry.group == PLUGIN_ENTRYPOINT_GROUP
    ]
    manifest = PluginManifest(
        name=str(distribution.metadata.get("Name", "")),
        version=str(distribution.version),
        description=str(distribution.metadata.get("Summary", "")),
        author=str(distribution.metadata.get("Author", "")),
        plugin_api_version=int(payload.get("plugin_api_version", 0)),
        orcheo_version=str(payload.get("orcheo_version", "")),
        exports=[
            str(export_name)
            for export_name in payload.get("exports", [])
            if isinstance(export_name, str)
        ],
        entry_points=entry_points,
    )
    return manifest, _sha256(manifest_file)


def _iter_plugin_distributions(
    site_packages: Path,
) -> list[importlib.metadata.Distribution]:
    """Return distributions that expose Orcheo plugin entry points."""
    distributions = list(importlib.metadata.distributions(path=[str(site_packages)]))
    plugin_distributions: list[importlib.metadata.Distribution] = []
    for distribution in distributions:
        if any(
            entry.group == PLUGIN_ENTRYPOINT_GROUP
            for entry in distribution.entry_points
        ):
            plugin_distributions.append(distribution)
    return plugin_distributions


def _load_plugin_manifests(site_packages: Path) -> list[tuple[PluginManifest, str]]:
    """Return manifests discovered in ``site_packages``."""
    return [
        _distribution_to_manifest(distribution)
        for distribution in _iter_plugin_distributions(site_packages)
    ]


def _import_plugin_entry_points(site_packages: Path) -> dict[str, str]:
    """Attempt to load every installed plugin entry point."""
    errors: dict[str, str] = {}
    with _temporary_sys_path(site_packages):
        for distribution in _iter_plugin_distributions(site_packages):
            for entry_point in distribution.entry_points:
                if entry_point.group != PLUGIN_ENTRYPOINT_GROUP:
                    continue
                try:
                    entry_point.load()
                except (
                    Exception
                ) as exc:  # pragma: no cover - exercised via doctor tests
                    name = str(distribution.metadata.get("Name", entry_point.name))
                    errors[name] = str(exc)
    return errors


def _install_refs_into_venv(venv_dir: Path, refs: list[str]) -> None:
    """Install plugin refs into ``venv_dir`` using ``uv pip``."""
    if not refs:
        return
    command = [
        "uv",
        "pip",
        "install",
        "--python",
        str(_venv_python(venv_dir)),
        *refs,
    ]
    result = _run_command(command)
    if result.returncode != 0:
        raise PluginError(result.stderr.strip() or "Plugin installation failed.")


def _validate_manifests(manifests: list[PluginManifest]) -> dict[str, list[str]]:
    """Return compatibility issues keyed by plugin name."""
    issues: dict[str, list[str]] = {}
    for manifest in manifests:
        manifest_issues = check_manifest_compatibility(manifest)
        if manifest_issues:
            issues[manifest.name] = manifest_issues
    return issues


def _write_manifest_cache(
    manifests_dir: Path, manifests: list[tuple[PluginManifest, str]]
) -> None:
    """Persist installed plugin manifests for diagnostics."""
    manifests_dir.mkdir(parents=True, exist_ok=True)
    for manifest, _manifest_hash in manifests:
        path = manifests_dir / f"{manifest.name}.json"
        payload = {
            "name": manifest.name,
            "version": manifest.version,
            "description": manifest.description,
            "author": manifest.author,
            "plugin_api_version": manifest.plugin_api_version,
            "orcheo_version": manifest.orcheo_version,
            "exports": manifest.exports,
            "entry_points": manifest.entry_points,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _rebuild_environment(
    *,
    refs: list[str],
    target_dir: Path,
    wheels_dir: Path,
    manifests_dir: Path,
) -> tuple[list[PluginManifest], list[LockedPluginRecord]]:
    """Build a plugin venv for ``refs`` and return the resolved lock state."""
    if target_dir.exists():
        shutil.rmtree(target_dir)
    if wheels_dir.exists():
        shutil.rmtree(wheels_dir)
    _ensure_venv(target_dir)
    wheels_dir.mkdir(parents=True, exist_ok=True)
    _install_refs_into_venv(target_dir, refs)
    site_packages = _site_packages(target_dir)
    manifests_with_hashes = _load_plugin_manifests(site_packages)
    manifests = [manifest for manifest, _ in manifests_with_hashes]
    issues = _validate_manifests(manifests)
    if issues:
        details = "; ".join(
            f"{name}: {', '.join(problem_list)}"
            for name, problem_list in issues.items()
        )
        raise PluginError(details)
    _write_manifest_cache(manifests_dir, manifests_with_hashes)
    locked_records: list[LockedPluginRecord] = []
    for manifest, manifest_hash in manifests_with_hashes:
        locked_records.append(
            LockedPluginRecord(
                name=manifest.name,
                version=manifest.version,
                plugin_api_version=manifest.plugin_api_version,
                orcheo_version=manifest.orcheo_version,
                location=str(target_dir),
                wheel_sha256="",
                manifest_sha256=manifest_hash,
                exports=manifest.exports,
                description=manifest.description,
                author=manifest.author,
                entry_points=manifest.entry_points,
            )
        )
    return manifests, locked_records


def _replace_directory(source: Path, destination: Path) -> None:
    """Atomically replace ``destination`` with ``source`` when possible."""
    backup = destination.with_name(f"{destination.name}.bak")
    if backup.exists():
        shutil.rmtree(backup)
    if destination.exists():
        os.replace(destination, backup)
    os.replace(source, destination)
    if backup.exists():
        shutil.rmtree(backup)


class PluginManager:
    """High-level interface for CLI-driven plugin lifecycle operations."""

    def __init__(self, paths: PluginStoragePaths | None = None) -> None:
        """Initialize the manager with explicit or default storage paths."""
        self.paths = paths or build_storage_paths()
        self.plugin_dir = Path(self.paths.plugin_dir)
        self.state_file = Path(self.paths.state_file)
        self.lock_file = Path(self.paths.lock_file)
        self.install_dir = Path(self.paths.install_dir)
        self.wheels_dir = Path(self.paths.wheels_dir)
        self.manifests_dir = Path(self.paths.manifests_dir)

    def list_plugins(self) -> list[dict[str, Any]]:
        """Return merged desired and resolved plugin state."""
        desired = {
            record.name: record for record in load_desired_state(self.state_file)
        }
        locked = {record.name: record for record in load_lock_state(self.lock_file)}
        rows: list[dict[str, Any]] = []
        for name in sorted(set(desired) | set(locked), key=str.lower):
            desired_record = desired.get(name)
            locked_record = locked.get(name)
            enabled = desired_record.enabled if desired_record is not None else False
            status = "disabled" if not enabled else "installed"
            if enabled and locked_record is None:
                status = "error"
            rows.append(
                {
                    "name": name,
                    "enabled": enabled,
                    "status": status,
                    "version": locked_record.version if locked_record else "",
                    "exports": locked_record.exports if locked_record else [],
                    "source": desired_record.source if desired_record else "",
                }
            )
        return rows

    def show_plugin(self, name: str) -> dict[str, Any]:
        """Return merged details for ``name``."""
        desired = {
            record.name: record for record in load_desired_state(self.state_file)
        }
        locked = {record.name: record for record in load_lock_state(self.lock_file)}
        if name not in desired and name not in locked:
            raise PluginError(f"Plugin '{name}' is not installed.")
        desired_record = desired.get(name)
        locked_record = locked.get(name)
        return {
            "name": name,
            "source": desired_record.source if desired_record else "",
            "enabled": desired_record.enabled if desired_record is not None else False,
            "status": "disabled"
            if desired_record is not None and not desired_record.enabled
            else ("installed" if locked_record is not None else "error"),
            "version": locked_record.version if locked_record else "",
            "plugin_api_version": locked_record.plugin_api_version
            if locked_record
            else None,
            "orcheo_version": locked_record.orcheo_version if locked_record else "",
            "exports": locked_record.exports if locked_record else [],
            "description": locked_record.description if locked_record else "",
            "author": locked_record.author if locked_record else "",
            "entry_points": locked_record.entry_points if locked_record else [],
            "location": locked_record.location if locked_record else "",
            "running_orcheo_version": get_running_orcheo_version(),
        }

    def _desired_by_name(self) -> dict[str, DesiredPluginRecord]:
        return {record.name: record for record in load_desired_state(self.state_file)}

    def _lock_by_name(self) -> dict[str, LockedPluginRecord]:
        return {record.name: record for record in load_lock_state(self.lock_file)}

    def _reconcile_desired_and_lock(
        self,
        desired_records: list[DesiredPluginRecord],
        locked_records: list[LockedPluginRecord],
    ) -> None:
        source_by_name = {record.name: record.source for record in desired_records}
        for locked_record in locked_records:
            source = source_by_name.get(locked_record.name)
            if source is not None:
                locked_record.wheel_sha256 = hash_install_source(source)
        save_desired_state(self.state_file, desired_records)
        save_lock_state(self.lock_file, locked_records)

    def _activate_build(
        self,
        *,
        desired_records: list[DesiredPluginRecord],
        validate: Callable[[list[PluginManifest]], None] | None = None,
        activate: bool = True,
    ) -> tuple[list[PluginManifest], list[LockedPluginRecord]]:
        desired_refs = [record.source for record in desired_records]
        self.plugin_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_root = Path(
            tempfile.mkdtemp(prefix="orcheo-plugin-build-", dir=self.plugin_dir.parent)
        )
        temp_venv = temp_root / "venv"
        temp_wheels = temp_root / "wheels"
        temp_manifests = temp_root / "manifests"
        try:
            if desired_refs:
                manifests, locked_records = _rebuild_environment(
                    refs=desired_refs,
                    target_dir=temp_venv,
                    wheels_dir=temp_wheels,
                    manifests_dir=temp_manifests,
                )
            else:
                manifests = []
                locked_records = []
                _ensure_venv(temp_venv)
            if validate is not None:
                validate(manifests)
            if not activate:
                return manifests, locked_records
            self.plugin_dir.mkdir(parents=True, exist_ok=True)
            if self.wheels_dir.exists():
                shutil.rmtree(self.wheels_dir)
            if temp_wheels.exists():
                shutil.copytree(temp_wheels, self.wheels_dir, dirs_exist_ok=True)
            if self.manifests_dir.exists():
                shutil.rmtree(self.manifests_dir)
            if temp_manifests.exists():
                shutil.copytree(temp_manifests, self.manifests_dir, dirs_exist_ok=True)
            _replace_directory(temp_venv, self.install_dir)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)
        return manifests, locked_records

    def install(self, ref: str) -> dict[str, Any]:
        """Install a plugin from a package, wheel, path, or git reference."""
        desired_records = load_desired_state(self.state_file)
        existing_names = {record.name for record in desired_records}
        candidate_records = list(desired_records)

        def _validate_single_new_plugin(manifests: list[PluginManifest]) -> None:
            new_plugins = [
                manifest
                for manifest in manifests
                if manifest.name not in existing_names
            ]
            if len(new_plugins) != 1:
                raise PluginError(
                    "Install reference must resolve to exactly one new plugin package."
                )

        manifests, locked_records = self._activate_build(
            desired_records=[
                *candidate_records,
                DesiredPluginRecord(name=f"pending:{ref}", source=ref, enabled=True),
            ],
            validate=_validate_single_new_plugin,
        )
        new_plugins = [
            manifest for manifest in manifests if manifest.name not in existing_names
        ]
        new_manifest = new_plugins[0]
        candidate_records = [
            record
            for record in candidate_records
            if not record.name.startswith("pending:")
        ]
        candidate_records.append(
            DesiredPluginRecord(
                name=new_manifest.name,
                source=ref,
                enabled=True,
                install_source="cli",
            )
        )
        impact = classify_plugin_change(
            previous=None,
            current=new_manifest,
            operation="install",
        )
        self._reconcile_desired_and_lock(candidate_records, locked_records)
        return {
            "plugin": self.show_plugin(new_manifest.name),
            "impact": impact,
        }

    def update(self, name: str) -> dict[str, Any]:
        """Rebuild the plugin environment using the stored source for ``name``."""
        impact = self.preview_update(name)
        desired = self._desired_by_name()
        desired_records = list(desired.values())
        _manifests, locked_records = self._activate_build(
            desired_records=desired_records
        )
        self._reconcile_desired_and_lock(desired_records, locked_records)
        return {
            "plugin": self.show_plugin(name),
            "impact": impact,
        }

    def preview_update(self, name: str) -> PluginImpactSummary:
        """Compute update impact for ``name`` without mutating plugin state."""
        desired = self._desired_by_name()
        previous_lock = self._lock_by_name()
        if name not in desired:
            raise PluginError(f"Plugin '{name}' is not installed.")
        desired_records = list(desired.values())
        manifests, _locked_records = self._activate_build(
            desired_records=desired_records,
            activate=False,
        )
        manifests_by_name = {manifest.name: manifest for manifest in manifests}
        if name not in manifests_by_name:
            raise PluginError(
                f"Updated environment no longer provides plugin '{name}'."
            )
        return classify_plugin_change(
            previous=previous_lock.get(name),
            current=manifests_by_name[name],
            operation="update",
        )

    def update_all(self) -> list[dict[str, Any]]:
        """Rebuild all desired plugins and return per-plugin impact summaries."""
        preview = self.preview_update_all()
        desired = self._desired_by_name()
        desired_records = list(desired.values())
        manifests, locked_records = self._activate_build(
            desired_records=desired_records
        )
        manifests_by_name = {manifest.name: manifest for manifest in manifests}
        self._reconcile_desired_and_lock(desired_records, locked_records)
        preview_by_name = {item["name"]: item["impact"] for item in preview}
        results: list[dict[str, Any]] = []
        for name in sorted(desired, key=str.lower):
            manifest = manifests_by_name.get(name)
            if manifest is None:
                continue
            results.append(
                {
                    "plugin": self.show_plugin(name),
                    "impact": preview_by_name[name],
                }
            )
        return results

    def preview_update_all(self) -> list[dict[str, Any]]:
        """Compute update impacts for all plugins without mutating plugin state."""
        desired = self._desired_by_name()
        previous_lock = self._lock_by_name()
        desired_records = list(desired.values())
        manifests, _locked_records = self._activate_build(
            desired_records=desired_records,
            activate=False,
        )
        manifests_by_name = {manifest.name: manifest for manifest in manifests}
        return [
            {
                "name": name,
                "impact": classify_plugin_change(
                    previous=previous_lock.get(name),
                    current=manifest,
                    operation="update",
                ),
            }
            for name in sorted(desired, key=str.lower)
            if (manifest := manifests_by_name.get(name)) is not None
        ]

    def uninstall(self, name: str) -> PluginImpactSummary:
        """Remove ``name`` from desired state and rebuild the plugin environment."""
        impact = self.preview_uninstall(name)
        desired = self._desired_by_name()
        desired_records = [record for record in desired.values() if record.name != name]
        _manifests, locked_records = self._activate_build(
            desired_records=desired_records
        )
        self._reconcile_desired_and_lock(desired_records, locked_records)
        return impact

    def preview_uninstall(self, name: str) -> PluginImpactSummary:
        """Compute uninstall impact for ``name`` without mutating plugin state."""
        desired = self._desired_by_name()
        locked = self._lock_by_name()
        if name not in desired:
            raise PluginError(f"Plugin '{name}' is not installed.")
        if name not in locked:
            raise PluginError(f"Plugin '{name}' is not locked.")
        manifest = PluginManifest(
            name=name,
            version=locked[name].version,
            description=locked[name].description,
            author=locked[name].author,
            plugin_api_version=locked[name].plugin_api_version,
            orcheo_version=locked[name].orcheo_version,
            exports=locked[name].exports,
            entry_points=locked[name].entry_points,
        )
        impact = classify_plugin_change(
            previous=locked[name],
            current=manifest,
            operation="uninstall",
        )
        return impact

    def set_enabled(self, name: str, *, enabled: bool) -> PluginImpactSummary:
        """Enable or disable a plugin."""
        impact = self.preview_set_enabled(name, enabled=enabled)
        desired = self._desired_by_name()
        desired[name].enabled = enabled
        desired_records = list(desired.values())
        _manifests, locked_records = self._activate_build(
            desired_records=desired_records
        )
        self._reconcile_desired_and_lock(desired_records, locked_records)
        return impact

    def preview_set_enabled(self, name: str, *, enabled: bool) -> PluginImpactSummary:
        """Compute enable or disable impact without mutating plugin state."""
        desired = self._desired_by_name()
        locked = self._lock_by_name()
        if name not in desired:
            raise PluginError(f"Plugin '{name}' is not installed.")
        if name not in locked:
            raise PluginError(f"Plugin '{name}' is not locked.")
        manifest = PluginManifest(
            name=name,
            version=locked[name].version,
            description=locked[name].description,
            author=locked[name].author,
            plugin_api_version=locked[name].plugin_api_version,
            orcheo_version=locked[name].orcheo_version,
            exports=locked[name].exports,
            entry_points=locked[name].entry_points,
        )
        return classify_plugin_change(
            previous=locked[name],
            current=manifest,
            operation="disable" if not enabled else "install",
        )

    def doctor(self) -> DoctorReport:
        """Inspect plugin state without making changes."""
        checks: list[DoctorCheck] = []
        checks.append(
            DoctorCheck(
                name="plugin_venv_exists",
                severity="WARN",
                ok=self.install_dir.exists()
                and _venv_python(self.install_dir).exists(),
                message=(
                    "plugin venv present"
                    if self.install_dir.exists()
                    and _venv_python(self.install_dir).exists()
                    else (
                        "plugin venv missing or corrupt — run "
                        "'orcheo plugin install' to rebuild"
                    )
                ),
            )
        )
        if self.install_dir.exists() and _venv_python(self.install_dir).exists():
            command = [str(_venv_python(self.install_dir)), "-c"]
            command.append(
                "import sys; "
                "print(f'{sys.version_info.major}.{sys.version_info.minor}')"
            )
            result = _run_command(command)
            venv_version = result.stdout.strip()
            current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
            checks.append(
                DoctorCheck(
                    name="plugin_venv_python_version",
                    severity="ERROR",
                    ok=venv_version == current_version,
                    message=(
                        "venv Python matches core Python"
                        if venv_version == current_version
                        else (
                            f"venv Python {venv_version} does not match core "
                            f"Python {current_version}"
                        )
                    ),
                )
            )
        desired = self._desired_by_name()
        locked = self._lock_by_name()
        site_packages = _site_packages(self.install_dir)
        if site_packages.exists():
            import_errors = _import_plugin_entry_points(site_packages)
            for name in sorted(
                plugin_name for plugin_name, record in desired.items() if record.enabled
            ):
                checks.append(
                    DoctorCheck(
                        name=f"plugin_importable:{name}",
                        severity="ERROR",
                        ok=name not in import_errors,
                        message=(
                            f"plugin {name} imported successfully"
                            if name not in import_errors
                            else (
                                f"plugin {name} failed to import: {import_errors[name]}"
                            )
                        ),
                    )
                )
            manifests_with_hashes = {
                manifest.name: (manifest, manifest_hash)
                for manifest, manifest_hash in _load_plugin_manifests(site_packages)
            }
            for name, record in desired.items():
                if not record.enabled:
                    continue
                lock_record = locked.get(name)
                manifest_entry = manifests_with_hashes.get(name)
                checks.append(
                    DoctorCheck(
                        name=f"lock_consistency:{name}",
                        severity="ERROR",
                        ok=lock_record is not None and manifest_entry is not None,
                        message=(
                            f"plugin {name} lock entry present"
                            if lock_record is not None and manifest_entry is not None
                            else f"plugin {name} is locked but not installed"
                        ),
                    )
                )
                if lock_record is None or manifest_entry is None:
                    continue
                manifest, manifest_hash = manifest_entry
                checks.append(
                    DoctorCheck(
                        name=f"manifest_sha256:{name}",
                        severity="ERROR",
                        ok=manifest_hash == lock_record.manifest_sha256,
                        message=(
                            f"plugin {name} manifest hash matches"
                            if manifest_hash == lock_record.manifest_sha256
                            else (
                                f"plugin {name} manifest hash mismatch — "
                                "reinstall required"
                            )
                        ),
                    )
                )
                checks.append(
                    DoctorCheck(
                        name=f"plugin_api_version:{name}",
                        severity="ERROR",
                        ok=manifest.plugin_api_version == PLUGIN_API_VERSION,
                        message=(
                            f"plugin {name} API version is compatible"
                            if manifest.plugin_api_version == PLUGIN_API_VERSION
                            else (
                                f"plugin {name} requires plugin API "
                                f"{manifest.plugin_api_version}, current is "
                                f"{PLUGIN_API_VERSION}"
                            )
                        ),
                    )
                )
                compatibility_issues = check_manifest_compatibility(manifest)
                version_warning = next(
                    (
                        issue
                        for issue in compatibility_issues
                        if "orcheo version" in issue
                    ),
                    None,
                )
                checks.append(
                    DoctorCheck(
                        name=f"orcheo_version:{name}",
                        severity="WARN",
                        ok=version_warning is None,
                        message=(
                            f"plugin {name} Orcheo version is compatible"
                            if version_warning is None
                            else (
                                f"plugin {name} declares orcheo_version "
                                f"{manifest.orcheo_version}, running "
                                f"{get_running_orcheo_version()}"
                            )
                        ),
                    )
                )
            referenced_disabled = _find_disabled_dependencies(
                desired=desired,
                site_packages=site_packages,
            )
            for disabled_name, referrers in referenced_disabled.items():
                checks.append(
                    DoctorCheck(
                        name=f"disabled_dependency:{disabled_name}",
                        severity="WARN",
                        ok=False,
                        message=(
                            f"plugin {disabled_name} is disabled but "
                            f"referenced by {', '.join(sorted(referrers))}"
                        ),
                    )
                )
        return DoctorReport(checks=checks)


def _find_disabled_dependencies(
    *,
    desired: dict[str, DesiredPluginRecord],
    site_packages: Path,
) -> dict[str, set[str]]:
    """Return disabled plugin names referenced by enabled plugin requirements."""
    disabled_names = {
        canonicalize_name(name)
        for name, record in desired.items()
        if not record.enabled
    }
    if not disabled_names:
        return {}
    referenced: dict[str, set[str]] = {}
    for distribution in _iter_plugin_distributions(site_packages):
        name = str(distribution.metadata.get("Name", ""))
        if not desired.get(name) or not desired[name].enabled:
            continue
        requirements = distribution.requires or []
        for requirement in requirements:
            dependency_name = canonicalize_name(
                requirement.split(";", maxsplit=1)[0]
                .split("[", maxsplit=1)[0]
                .split(" ", maxsplit=1)[0]
            )
            if dependency_name in disabled_names:
                referenced.setdefault(dependency_name, set()).add(name)
    return referenced


def _hash_directory(path: Path) -> str:
    """Return a stable hash for the contents of ``path``."""
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(child.relative_to(path)).encode("utf-8"))
        digest.update(child.read_bytes())
    return digest.hexdigest()


def hash_install_source(source: str) -> str:
    """Return a deterministic hash for a plugin install reference."""
    path = Path(source).expanduser()
    if path.is_file():
        return _sha256(path)
    if path.is_dir():
        return _hash_directory(path)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


__all__ = ["PLUGIN_ENTRYPOINT_GROUP", "PluginError", "PluginManager"]
