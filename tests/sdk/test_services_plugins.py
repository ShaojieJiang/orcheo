"""Tests for plugin service operations."""

from __future__ import annotations
from unittest.mock import MagicMock, patch
from orcheo_sdk.services.plugins import (
    disable_plugin_data,
    doctor_plugins_data,
    enable_plugin_data,
    install_plugin_data,
    list_plugins_data,
    preview_disable_plugin_data,
    preview_enable_plugin_data,
    preview_uninstall_plugin_data,
    preview_update_all_plugins_data,
    preview_update_plugin_data,
    show_plugin_data,
    uninstall_plugin_data,
    update_all_plugins_data,
    update_plugin_data,
)


def test_update_all_plugins_data_calls_update_all_and_invalidates() -> None:
    """update_all_plugins_data calls update_all, invalidates loader, returns data."""
    expected = [{"plugin": {"name": "my-plugin"}, "impact": MagicMock()}]
    mock_manager = MagicMock()
    mock_manager.update_all.return_value = expected

    with patch("orcheo_sdk.services.plugins.PluginManager", return_value=mock_manager):
        with patch("orcheo_sdk.services.plugins.invalidate_plugin_loader") as mock_inv:
            result = update_all_plugins_data()

    mock_manager.update_all.assert_called_once()
    mock_inv.assert_called_once()
    assert result is expected


def test_preview_update_all_plugins_data_returns_manager_result() -> None:
    """preview_update_all_plugins_data returns PluginManager().preview_update_all()."""
    expected = [{"name": "my-plugin", "impact": MagicMock()}]
    mock_manager = MagicMock()
    mock_manager.preview_update_all.return_value = expected

    with patch("orcheo_sdk.services.plugins.PluginManager", return_value=mock_manager):
        result = preview_update_all_plugins_data()

    mock_manager.preview_update_all.assert_called_once()
    assert result is expected


def test_list_plugins_data_returns_manager_list() -> None:
    """list_plugins_data returns PluginManager().list_plugins()."""
    expected = [{"name": "p1"}]
    mock_manager = MagicMock()
    mock_manager.list_plugins.return_value = expected

    with patch("orcheo_sdk.services.plugins.PluginManager", return_value=mock_manager):
        result = list_plugins_data()

    mock_manager.list_plugins.assert_called_once()
    assert result is expected


def test_show_plugin_data_returns_manager_show() -> None:
    """show_plugin_data returns PluginManager().show_plugin(name)."""
    expected = {"name": "p1", "version": "1.0.0"}
    mock_manager = MagicMock()
    mock_manager.show_plugin.return_value = expected

    with patch("orcheo_sdk.services.plugins.PluginManager", return_value=mock_manager):
        result = show_plugin_data("p1")

    mock_manager.show_plugin.assert_called_once_with("p1")
    assert result is expected


def test_install_plugin_data_invalidates_loader() -> None:
    """install_plugin_data installs, invalidates loader, returns result."""
    expected = {"name": "p1"}
    mock_manager = MagicMock()
    mock_manager.install.return_value = expected

    with patch("orcheo_sdk.services.plugins.PluginManager", return_value=mock_manager):
        with patch("orcheo_sdk.services.plugins.invalidate_plugin_loader") as mock_inv:
            result = install_plugin_data("./p1")

    mock_manager.install.assert_called_once_with("./p1")
    mock_inv.assert_called_once()
    assert result is expected


def test_update_plugin_data_invalidates_loader() -> None:
    """update_plugin_data updates single plugin, invalidates loader, returns result."""
    expected = {"name": "p1"}
    mock_manager = MagicMock()
    mock_manager.update.return_value = expected

    with patch("orcheo_sdk.services.plugins.PluginManager", return_value=mock_manager):
        with patch("orcheo_sdk.services.plugins.invalidate_plugin_loader") as mock_inv:
            result = update_plugin_data("p1")

    mock_manager.update.assert_called_once_with("p1")
    mock_inv.assert_called_once()
    assert result is expected


def test_preview_update_plugin_data_returns_name_and_impact() -> None:
    """preview_update_plugin_data returns dict with name and impact."""
    mock_impact = MagicMock()
    mock_manager = MagicMock()
    mock_manager.preview_update.return_value = mock_impact

    with patch("orcheo_sdk.services.plugins.PluginManager", return_value=mock_manager):
        result = preview_update_plugin_data("p1")

    mock_manager.preview_update.assert_called_once_with("p1")
    assert result == {"name": "p1", "impact": mock_impact}


def test_uninstall_plugin_data_invalidates_loader() -> None:
    """uninstall_plugin_data uninstalls, invalidates loader, returns result."""
    mock_impact = MagicMock()
    mock_manager = MagicMock()
    mock_manager.uninstall.return_value = mock_impact

    with patch("orcheo_sdk.services.plugins.PluginManager", return_value=mock_manager):
        with patch("orcheo_sdk.services.plugins.invalidate_plugin_loader") as mock_inv:
            result = uninstall_plugin_data("p1")

    mock_manager.uninstall.assert_called_once_with("p1")
    mock_inv.assert_called_once()
    assert result == {"name": "p1", "impact": mock_impact}


def test_preview_uninstall_plugin_data_returns_name_and_impact() -> None:
    """preview_uninstall_plugin_data returns dict with name and impact."""
    mock_impact = MagicMock()
    mock_manager = MagicMock()
    mock_manager.preview_uninstall.return_value = mock_impact

    with patch("orcheo_sdk.services.plugins.PluginManager", return_value=mock_manager):
        result = preview_uninstall_plugin_data("p1")

    mock_manager.preview_uninstall.assert_called_once_with("p1")
    assert result == {"name": "p1", "impact": mock_impact}


def test_enable_plugin_data_invalidates_loader() -> None:
    """enable_plugin_data enables plugin, invalidates loader, returns result."""
    mock_impact = MagicMock()
    mock_manager = MagicMock()
    mock_manager.set_enabled.return_value = mock_impact

    with patch("orcheo_sdk.services.plugins.PluginManager", return_value=mock_manager):
        with patch("orcheo_sdk.services.plugins.invalidate_plugin_loader") as mock_inv:
            result = enable_plugin_data("p1")

    mock_manager.set_enabled.assert_called_once_with("p1", enabled=True)
    mock_inv.assert_called_once()
    assert result == {"name": "p1", "impact": mock_impact}


def test_preview_enable_plugin_data_returns_name_and_impact() -> None:
    """preview_enable_plugin_data returns dict with name and impact."""
    mock_impact = MagicMock()
    mock_manager = MagicMock()
    mock_manager.preview_set_enabled.return_value = mock_impact

    with patch("orcheo_sdk.services.plugins.PluginManager", return_value=mock_manager):
        result = preview_enable_plugin_data("p1")

    mock_manager.preview_set_enabled.assert_called_once_with("p1", enabled=True)
    assert result == {"name": "p1", "impact": mock_impact}


def test_disable_plugin_data_invalidates_loader() -> None:
    """disable_plugin_data disables plugin, invalidates loader, returns result."""
    mock_impact = MagicMock()
    mock_manager = MagicMock()
    mock_manager.set_enabled.return_value = mock_impact

    with patch("orcheo_sdk.services.plugins.PluginManager", return_value=mock_manager):
        with patch("orcheo_sdk.services.plugins.invalidate_plugin_loader") as mock_inv:
            result = disable_plugin_data("p1")

    mock_manager.set_enabled.assert_called_once_with("p1", enabled=False)
    mock_inv.assert_called_once()
    assert result == {"name": "p1", "impact": mock_impact}


def test_preview_disable_plugin_data_returns_name_and_impact() -> None:
    """preview_disable_plugin_data returns dict with name and impact."""
    mock_impact = MagicMock()
    mock_manager = MagicMock()
    mock_manager.preview_set_enabled.return_value = mock_impact

    with patch("orcheo_sdk.services.plugins.PluginManager", return_value=mock_manager):
        result = preview_disable_plugin_data("p1")

    mock_manager.preview_set_enabled.assert_called_once_with("p1", enabled=False)
    assert result == {"name": "p1", "impact": mock_impact}


def test_doctor_plugins_data_returns_serializable_report() -> None:
    """doctor_plugins_data returns serializable dict from PluginManager().doctor()."""
    mock_check = MagicMock()
    mock_check.name = "import-check"
    mock_check.severity = "ERROR"
    mock_check.ok = False
    mock_check.message = "Failed to import"
    mock_report = MagicMock()
    mock_report.checks = [mock_check]
    mock_report.has_errors = True
    mock_manager = MagicMock()
    mock_manager.doctor.return_value = mock_report

    with patch("orcheo_sdk.services.plugins.PluginManager", return_value=mock_manager):
        result = doctor_plugins_data()

    mock_manager.doctor.assert_called_once()
    assert result["has_errors"] is True
    assert result["checks"] == [
        {
            "name": "import-check",
            "severity": "ERROR",
            "ok": False,
            "message": "Failed to import",
        }
    ]
