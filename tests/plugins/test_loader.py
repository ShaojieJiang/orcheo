"""Tests for runtime plugin loading and in-process reload behavior."""

from __future__ import annotations
import shutil
import sys
from pathlib import Path
import pytest
from orcheo.nodes.registry import registry
from orcheo.plugins import load_enabled_plugins, reset_plugin_loader_for_tests
from orcheo.plugins.manager import PluginManager
from orcheo.triggers.registry import trigger_registry


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "plugin_fixtures"


def _copy_fixture(tmp_path: Path, fixture_name: str) -> Path:
    source = FIXTURE_ROOT / fixture_name
    destination = tmp_path / fixture_name
    shutil.copytree(source, destination)
    return destination


def _site_packages(plugin_dir: Path) -> Path:
    return (
        plugin_dir
        / "venv"
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )


def _set_plugin_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    plugin_dir = tmp_path / "plugins"
    cache_dir = tmp_path / "cache"
    config_dir = tmp_path / "config"
    plugin_dir.mkdir()
    cache_dir.mkdir()
    config_dir.mkdir()
    monkeypatch.setenv("ORCHEO_PLUGIN_DIR", str(plugin_dir))
    monkeypatch.setenv("ORCHEO_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("ORCHEO_CONFIG_DIR", str(config_dir))
    return plugin_dir


def test_loader_isolates_broken_plugin_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A broken plugin should not block unrelated healthy plugins from loading."""
    _set_plugin_env(monkeypatch, tmp_path)
    manager = PluginManager()
    manager.install(str(_copy_fixture(tmp_path, "node_plugin")))
    manager.install(str(_copy_fixture(tmp_path, "broken_plugin")))

    reset_plugin_loader_for_tests()
    report = load_enabled_plugins(force=True)
    results = {item.name: item for item in report.results}

    assert results["orcheo-plugin-fixture-node"].loaded is True
    assert results["orcheo-plugin-fixture-broken"].loaded is False
    assert "broken fixture plugin import" in (
        results["orcheo-plugin-fixture-broken"].error or ""
    )
    assert registry.get_node("FixturePluginNode") is not None


def test_loader_skips_disabled_plugins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Disabled plugins remain installed but are not loaded into registries."""
    _set_plugin_env(monkeypatch, tmp_path)
    manager = PluginManager()
    manager.install(str(_copy_fixture(tmp_path, "node_plugin")))
    manager.set_enabled("orcheo-plugin-fixture-node", enabled=False)

    reset_plugin_loader_for_tests()
    report = load_enabled_plugins(force=True)

    assert report.results == []
    assert registry.get_node("FixturePluginNode") is None


def test_loader_reports_incompatible_manifest_at_startup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Startup should skip incompatible manifests with a precise diagnostic."""
    plugin_dir = _set_plugin_env(monkeypatch, tmp_path)
    manager = PluginManager()
    manager.install(str(_copy_fixture(tmp_path, "node_plugin")))

    manifest_path = (
        _site_packages(plugin_dir) / "orcheo_plugin_fixture_node" / "orcheo_plugin.toml"
    )
    manifest_path.write_text(
        'plugin_api_version = 999\norcheo_version = ">=0.0.0"\nexports = ["nodes"]\n',
        encoding="utf-8",
    )

    reset_plugin_loader_for_tests()
    report = load_enabled_plugins(force=True)
    results = {item.name: item for item in report.results}

    assert results["orcheo-plugin-fixture-node"].loaded is False
    assert "plugin API mismatch" in (results["orcheo-plugin-fixture-node"].error or "")
    assert registry.get_node("FixturePluginNode") is None


def test_loader_registers_trigger_plugins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Trigger plugins should register into the external trigger registry."""
    _set_plugin_env(monkeypatch, tmp_path)
    manager = PluginManager()
    manager.install(str(_copy_fixture(tmp_path, "trigger_plugin")))

    reset_plugin_loader_for_tests()
    report = load_enabled_plugins(force=True)

    assert {item.name for item in report.results} == {"orcheo-plugin-fixture-trigger"}
    registration = trigger_registry.get("fixture-trigger")
    assert registration is not None
    assert registration.metadata.display_name == "Fixture Trigger"
    assert registration.factory(enabled=True) == {
        "kind": "fixture-trigger",
        "config": {"enabled": True},
    }


@pytest.mark.asyncio()
async def test_loader_hot_reload_reimports_updated_plugin_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Force reloading should pick up updated plugin code for new runs."""
    _set_plugin_env(monkeypatch, tmp_path)
    manager = PluginManager()
    fixture_path = _copy_fixture(tmp_path, "node_plugin")
    manager.install(str(fixture_path))

    reset_plugin_loader_for_tests()
    first_report = load_enabled_plugins(force=True)
    node_v1 = registry.get_node("FixturePluginNode")
    assert node_v1 is not None

    first_value = await node_v1(name="fixture").run({}, {})
    assert first_value == {"value": "fixture-node"}

    module_path = fixture_path / "src" / "orcheo_plugin_fixture_node" / "__init__.py"
    module_path.write_text(
        module_path.read_text(encoding="utf-8").replace(
            '{"value": "fixture-node"}',
            '{"value": "fixture-node-v2"}',
        ),
        encoding="utf-8",
    )
    pyproject_path = fixture_path / "pyproject.toml"
    pyproject_path.write_text(
        pyproject_path.read_text(encoding="utf-8").replace(
            'version = "0.1.0"',
            'version = "0.2.0"',
        ),
        encoding="utf-8",
    )

    manager.update("orcheo-plugin-fixture-node")
    second_report = load_enabled_plugins(force=True)
    node_v2 = registry.get_node("FixturePluginNode")
    assert node_v2 is not None

    second_value = await node_v2(name="fixture").run({}, {})
    legacy_value = await node_v1(name="fixture").run({}, {})

    assert second_report.generation > first_report.generation
    assert second_value == {"value": "fixture-node-v2"}
    assert legacy_value == {"value": "fixture-node"}
