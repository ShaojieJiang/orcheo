"""Tests for plugin lifecycle CLI commands."""

from __future__ import annotations
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner
from orcheo_sdk.cli.main import app


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "plugin_fixtures"
VALIDATION_PLUGIN_ROOT = Path(__file__).resolve().parents[2] / "packages" / "plugins"


def _copy_fixture(tmp_path: Path, fixture_name: str) -> Path:
    source = FIXTURE_ROOT / fixture_name
    destination = tmp_path / fixture_name
    shutil.copytree(source, destination)
    return destination


def _plugin_dir(env: dict[str, str]) -> Path:
    return Path(env["ORCHEO_PLUGIN_DIR"])


def test_plugin_list_empty(runner: CliRunner, machine_env: dict[str, str]) -> None:
    """Machine mode renders empty output when no plugins are installed."""
    result = runner.invoke(app, ["plugin", "list"], env=machine_env)
    assert result.exit_code == 0
    assert result.stdout.strip() == "(empty)"


def test_plugin_install_list_and_show(
    runner: CliRunner, machine_env: dict[str, str], tmp_path: Path
) -> None:
    """Install a local plugin fixture and expose it through list/show."""
    fixture_path = _copy_fixture(tmp_path, "node_plugin")

    install_result = runner.invoke(
        app, ["plugin", "install", str(fixture_path)], env=machine_env
    )
    assert install_result.exit_code == 0
    install_payload = json.loads(install_result.stdout)
    assert install_payload["plugin"]["name"] == "orcheo-plugin-fixture-node"

    list_result = runner.invoke(app, ["plugin", "list"], env=machine_env)
    assert list_result.exit_code == 0
    assert "orcheo-plugin-fixture-node" in list_result.stdout

    show_result = runner.invoke(
        app,
        ["plugin", "show", "orcheo-plugin-fixture-node"],
        env=machine_env,
    )
    assert show_result.exit_code == 0
    show_payload = json.loads(show_result.stdout)
    assert show_payload["plugin_api_version"] == 1
    assert show_payload["exports"] == ["nodes"]

    plugin_dir = _plugin_dir(machine_env)
    assert (plugin_dir / "plugins.toml").exists()
    assert (plugin_dir / "plugin-lock.toml").exists()
    assert (plugin_dir / "venv").exists()

    node_list_result = runner.invoke(app, ["node", "list"], env=machine_env)
    assert node_list_result.exit_code == 0
    assert "FixturePluginNode" in node_list_result.stdout


def test_plugin_install_machine_mode_returns_json(
    runner: CliRunner, machine_env: dict[str, str], tmp_path: Path
) -> None:
    """Machine mode returns structured install output."""
    fixture_path = _copy_fixture(tmp_path, "edge_plugin")

    result = runner.invoke(
        app, ["plugin", "install", str(fixture_path)], env=machine_env
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["plugin"]["name"] == "orcheo-plugin-fixture-edge"
    assert payload["impact"]["activation_mode"] == "silent_hot_reload"

    edge_list_result = runner.invoke(app, ["edge", "list"], env=machine_env)
    assert edge_list_result.exit_code == 0
    assert "FixturePluginEdge" in edge_list_result.stdout


def test_validation_listener_plugins_install_via_cli(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """The shipped WeCom and Lark validation plugins install through the CLI."""
    wecom_result = runner.invoke(
        app,
        ["plugin", "install", str(VALIDATION_PLUGIN_ROOT / "wecom_listener")],
        env=machine_env,
    )
    assert wecom_result.exit_code == 0

    lark_result = runner.invoke(
        app,
        ["plugin", "install", str(VALIDATION_PLUGIN_ROOT / "lark_listener")],
        env=machine_env,
    )
    assert lark_result.exit_code == 0

    list_result = runner.invoke(app, ["plugin", "list"], env=machine_env)
    assert list_result.exit_code == 0
    assert "orcheo-plugin-wecom-listener" in list_result.stdout
    assert "orcheo-plugin-lark-listener" in list_result.stdout


def test_plugin_update_prompts_for_existing_hot_reloadable_plugin(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Updating an existing node plugin prompts for confirmation."""
    fixture_path = _copy_fixture(tmp_path, "node_plugin")
    result = runner.invoke(app, ["plugin", "install", str(fixture_path)], env=env)
    assert result.exit_code == 0

    pyproject_path = fixture_path / "pyproject.toml"
    pyproject_path.write_text(
        pyproject_path.read_text(encoding="utf-8").replace(
            'version = "0.1.0"', 'version = "0.2.0"'
        ),
        encoding="utf-8",
    )

    update_result = runner.invoke(
        app,
        ["plugin", "update", "orcheo-plugin-fixture-node"],
        env=env,
        input="y\n",
    )
    assert update_result.exit_code == 0
    assert "Update orcheo-plugin-fixture-node" in update_result.stdout

    show_result = runner.invoke(
        app,
        ["plugin", "show", "orcheo-plugin-fixture-node"],
        env=env,
    )
    assert show_result.exit_code == 0
    assert "0.2.0" in show_result.stdout


def test_plugin_disable_and_enable(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Disable and re-enable a listener plugin."""
    fixture_path = _copy_fixture(tmp_path, "listener_plugin")
    result = runner.invoke(app, ["plugin", "install", str(fixture_path)], env=env)
    assert result.exit_code == 0

    disable_result = runner.invoke(
        app,
        ["plugin", "disable", "orcheo-plugin-fixture-listener"],
        env=env,
        input="y\n",
    )
    assert disable_result.exit_code == 0
    assert "Disable orcheo-plugin-fixture-listener" in disable_result.stdout

    show_disabled = runner.invoke(
        app,
        ["plugin", "show", "orcheo-plugin-fixture-listener"],
        env=env,
    )
    assert show_disabled.exit_code == 0
    assert "'enabled': False" in show_disabled.stdout

    enable_result = runner.invoke(
        app,
        ["plugin", "enable", "orcheo-plugin-fixture-listener", "--force"],
        env=env,
    )
    assert enable_result.exit_code == 0

    show_enabled = runner.invoke(
        app,
        ["plugin", "show", "orcheo-plugin-fixture-listener"],
        env=env,
    )
    assert show_enabled.exit_code == 0
    assert "'enabled': True" in show_enabled.stdout


def test_plugin_listener_registration_is_available_to_compiler(
    runner: CliRunner,
    machine_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Installing a listener plugin makes its platform available to compilation."""
    from uuid import uuid4
    from orcheo.listeners.compiler import compile_listener_subscriptions
    from orcheo.plugins import reset_plugin_loader_for_tests

    fixture_path = _copy_fixture(tmp_path, "listener_plugin")
    result = runner.invoke(
        app, ["plugin", "install", str(fixture_path)], env=machine_env
    )
    assert result.exit_code == 0

    for key, value in machine_env.items():
        monkeypatch.setenv(key, value)

    reset_plugin_loader_for_tests()
    subscriptions = compile_listener_subscriptions(
        uuid4(),
        uuid4(),
        {
            "index": {
                "listeners": [
                    {
                        "node_name": "fixture",
                        "platform": "fixture-listener",
                        "credential_ref": "fixture-credential",
                    }
                ]
            }
        },
    )
    assert len(subscriptions) == 1
    assert subscriptions[0].platform == "fixture-listener"
    assert subscriptions[0].bot_identity_key == "fixture-listener:fixture-credential"


def test_plugin_uninstall_rebuilds_environment(
    runner: CliRunner, machine_env: dict[str, str], tmp_path: Path
) -> None:
    """Uninstall removes the plugin from desired and resolved state."""
    fixture_path = _copy_fixture(tmp_path, "node_plugin")
    result = runner.invoke(
        app, ["plugin", "install", str(fixture_path)], env=machine_env
    )
    assert result.exit_code == 0

    uninstall_result = runner.invoke(
        app,
        ["plugin", "uninstall", "orcheo-plugin-fixture-node", "--force"],
        env=machine_env,
    )
    assert uninstall_result.exit_code == 0
    payload = json.loads(uninstall_result.stdout)
    assert payload["name"] == "orcheo-plugin-fixture-node"

    list_result = runner.invoke(app, ["plugin", "list"], env=machine_env)
    assert list_result.exit_code == 0
    assert list_result.stdout.strip() == "(empty)"


def test_plugin_uninstall_prompt_happens_before_mutation(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Declining uninstall confirmation should leave plugin state unchanged."""
    fixture_path = _copy_fixture(tmp_path, "node_plugin")
    install_result = runner.invoke(
        app, ["plugin", "install", str(fixture_path)], env=env
    )
    assert install_result.exit_code == 0

    uninstall_result = runner.invoke(
        app,
        ["plugin", "uninstall", "orcheo-plugin-fixture-node"],
        env=env,
        input="n\n",
    )
    assert uninstall_result.exit_code == 1

    show_result = runner.invoke(
        app,
        ["plugin", "show", "orcheo-plugin-fixture-node"],
        env=env,
    )
    assert show_result.exit_code == 0


def test_plugin_update_prompt_happens_before_mutation(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Declining update confirmation should not rebuild to newer plugin version."""
    fixture_path = _copy_fixture(tmp_path, "node_plugin")
    install_result = runner.invoke(
        app, ["plugin", "install", str(fixture_path)], env=env
    )
    assert install_result.exit_code == 0

    pyproject_path = fixture_path / "pyproject.toml"
    pyproject_path.write_text(
        pyproject_path.read_text(encoding="utf-8").replace(
            'version = "0.1.0"', 'version = "0.2.0"'
        ),
        encoding="utf-8",
    )

    update_result = runner.invoke(
        app,
        ["plugin", "update", "orcheo-plugin-fixture-node"],
        env=env,
        input="n\n",
    )
    assert update_result.exit_code == 1

    show_result = runner.invoke(
        app,
        ["plugin", "show", "orcheo-plugin-fixture-node"],
        env=env,
    )
    assert show_result.exit_code == 0
    assert "0.1.0" in show_result.stdout


def test_plugin_doctor_reports_broken_plugin(
    runner: CliRunner, machine_env: dict[str, str], tmp_path: Path
) -> None:
    """Doctor surfaces import failures as errors."""
    fixture_path = _copy_fixture(tmp_path, "broken_plugin")
    install_result = runner.invoke(
        app,
        ["plugin", "install", str(fixture_path)],
        env=machine_env,
    )
    assert install_result.exit_code == 0

    doctor_result = runner.invoke(app, ["plugin", "doctor"], env=machine_env)
    assert doctor_result.exit_code == 1
    payload = json.loads(doctor_result.stdout)
    assert payload["has_errors"] is True
    assert any("failed to import" in check["message"] for check in payload["checks"])


def test_plugin_install_incompatible_manifest_is_transactional(
    runner: CliRunner, machine_env: dict[str, str], tmp_path: Path
) -> None:
    """Failed installs do not leave desired state or an activated plugin venv behind."""
    fixture_path = _copy_fixture(tmp_path, "incompatible_plugin")
    result = runner.invoke(
        app, ["plugin", "install", str(fixture_path)], env=machine_env
    )
    assert result.exit_code != 0

    plugin_dir = _plugin_dir(machine_env)
    state_file = plugin_dir / "plugins.toml"
    lock_file = plugin_dir / "plugin-lock.toml"

    assert not state_file.exists() or not state_file.read_text(encoding="utf-8").strip()
    assert not lock_file.exists() or not lock_file.read_text(encoding="utf-8").strip()

    list_result = runner.invoke(app, ["plugin", "list"], env=machine_env)
    assert list_result.exit_code == 0
    assert list_result.stdout.strip() == "(empty)"


def test_plugin_list_human_mode_render_table(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Human mode renders a table instead of machine output (line 91)."""
    mock_rows = [
        {
            "name": "orcheo-plugin-fixture-node",
            "enabled": True,
            "status": "installed",
            "version": "0.1.0",
            "exports": ["nodes"],
            "source": "/path/to/plugin",
        }
    ]
    with patch("orcheo_sdk.cli.plugin.list_plugins_data", return_value=mock_rows):
        result = runner.invoke(app, ["plugin", "list"], env=env)
    assert result.exit_code == 0
    # Human mode shows a rich table (machine mode shows markdown)
    assert "Installed Plugins" in result.stdout
    assert "orcheo-plugin-f" in result.stdout


def test_plugin_show_error_nonexistent(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """show_plugin raises BadParameter when plugin not found (lines 116-117)."""
    result = runner.invoke(
        app, ["plugin", "show", "nonexistent-plugin"], env=machine_env
    )
    assert result.exit_code != 0


def test_plugin_update_no_name_no_all_raises(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """update with no name and no --all raises BadParameter (line 206)."""
    result = runner.invoke(app, ["plugin", "update"], env=machine_env)
    assert result.exit_code != 0
    assert "Provide a plugin name" in result.output


def test_plugin_update_single_preview_error(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """update single raises BadParameter on preview PluginError (lines 209-210)."""
    result = runner.invoke(
        app, ["plugin", "update", "nonexistent-plugin"], env=machine_env
    )
    assert result.exit_code != 0


def test_plugin_update_single_machine_mode_output(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """update single in machine mode prints JSON and returns (lines 226-232)."""
    mock_impact = MagicMock()
    mock_impact.prompt_required = False
    mock_impact.activation_mode = "silent_hot_reload"
    mock_preview = {"name": "my-plugin", "impact": mock_impact}
    mock_plugin = {"name": "my-plugin", "version": "0.2.0"}
    mock_payload = {"plugin": mock_plugin, "impact": mock_impact}

    with patch(
        "orcheo_sdk.cli.plugin.preview_update_plugin_data",
        return_value=mock_preview,
    ):
        with patch(
            "orcheo_sdk.cli.plugin.update_plugin_data",
            return_value=mock_payload,
        ):
            result = runner.invoke(
                app,
                ["plugin", "update", "my-plugin", "--force"],
                env=machine_env,
            )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["plugin"]["name"] == "my-plugin"
    assert "impact" in payload


def test_plugin_update_single_error_in_update_data(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """update_plugin_data raises BadParameter (lines 223-224)."""
    from orcheo.plugins.manager import PluginError

    mock_impact = MagicMock()
    mock_impact.prompt_required = False
    mock_impact.activation_mode = "silent_hot_reload"
    mock_preview = {"name": "my-plugin", "impact": mock_impact}

    with patch(
        "orcheo_sdk.cli.plugin.preview_update_plugin_data",
        return_value=mock_preview,
    ):
        with patch(
            "orcheo_sdk.cli.plugin.update_plugin_data",
            side_effect=PluginError("update failed"),
        ):
            result = runner.invoke(
                app,
                ["plugin", "update", "my-plugin", "--force"],
                env=machine_env,
            )
    assert result.exit_code != 0


def test_plugin_update_all_no_plugins_machine_mode(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """update --all with no installed plugins outputs empty JSON (lines 181-191)."""
    with patch(
        "orcheo_sdk.cli.plugin.preview_update_all_plugins_data",
        return_value=[],
    ):
        with patch(
            "orcheo_sdk.cli.plugin.update_all_plugins_data",
            return_value=[],
        ):
            result = runner.invoke(
                app, ["plugin", "update", "--all", "--force"], env=machine_env
            )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == []


def test_plugin_update_all_human_mode(runner: CliRunner, env: dict[str, str]) -> None:
    """update --all in human mode uses render_json (lines 192-202)."""
    mock_impact = MagicMock()
    mock_impact.prompt_required = False
    mock_impact.activation_mode = "silent_hot_reload"
    mock_preview = [{"name": "my-plugin", "impact": mock_impact}]
    mock_plugin = {"name": "my-plugin", "version": "0.2.0"}
    mock_payload = [{"plugin": mock_plugin, "impact": mock_impact}]

    with patch(
        "orcheo_sdk.cli.plugin.preview_update_all_plugins_data",
        return_value=mock_preview,
    ):
        with patch(
            "orcheo_sdk.cli.plugin.update_all_plugins_data",
            return_value=mock_payload,
        ):
            result = runner.invoke(
                app, ["plugin", "update", "--all", "--force"], env=env
            )
    assert result.exit_code == 0


def test_plugin_update_all_preview_error(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """update --all raises BadParameter on preview PluginError (lines 165-166)."""
    from orcheo.plugins.manager import PluginError

    with patch(
        "orcheo_sdk.cli.plugin.preview_update_all_plugins_data",
        side_effect=PluginError("preview failed"),
    ):
        result = runner.invoke(
            app, ["plugin", "update", "--all", "--force"], env=machine_env
        )
    assert result.exit_code != 0


def test_plugin_update_all_update_error(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """update --all raises BadParameter on update_all_plugins_data PluginError."""
    from orcheo.plugins.manager import PluginError

    mock_impact = MagicMock()
    mock_impact.prompt_required = False
    mock_impact.activation_mode = "silent_hot_reload"
    mock_preview = [{"name": "some-plugin", "impact": mock_impact}]

    with patch(
        "orcheo_sdk.cli.plugin.preview_update_all_plugins_data",
        return_value=mock_preview,
    ):
        with patch(
            "orcheo_sdk.cli.plugin.update_all_plugins_data",
            side_effect=PluginError("update all failed"),
        ):
            result = runner.invoke(
                app, ["plugin", "update", "--all", "--force"], env=machine_env
            )
    assert result.exit_code != 0


def test_plugin_uninstall_preview_error(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """uninstall raises BadParameter on preview PluginError (lines 250-251)."""
    result = runner.invoke(
        app, ["plugin", "uninstall", "nonexistent-plugin", "--force"], env=machine_env
    )
    assert result.exit_code != 0


def test_plugin_uninstall_data_error(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """uninstall_plugin_data raises BadParameter (lines 261-262)."""
    from orcheo.plugins.manager import PluginError

    mock_impact = MagicMock()
    mock_impact.prompt_required = False
    mock_impact.activation_mode = "silent_hot_reload"
    mock_preview = {"name": "my-plugin", "impact": mock_impact}

    with patch(
        "orcheo_sdk.cli.plugin.preview_uninstall_plugin_data",
        return_value=mock_preview,
    ):
        with patch(
            "orcheo_sdk.cli.plugin.uninstall_plugin_data",
            side_effect=PluginError("uninstall failed"),
        ):
            result = runner.invoke(
                app,
                ["plugin", "uninstall", "my-plugin", "--force"],
                env=machine_env,
            )
    assert result.exit_code != 0


def test_plugin_uninstall_human_mode_output(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Uninstall in human mode prints confirmation message (lines 267-268)."""
    mock_impact = MagicMock()
    mock_impact.prompt_required = False
    mock_impact.activation_mode = "silent_hot_reload"
    mock_preview = {"name": "my-plugin", "impact": mock_impact}
    mock_payload = {"name": "my-plugin", "impact": mock_impact}

    with patch(
        "orcheo_sdk.cli.plugin.preview_uninstall_plugin_data",
        return_value=mock_preview,
    ):
        with patch(
            "orcheo_sdk.cli.plugin.uninstall_plugin_data",
            return_value=mock_payload,
        ):
            result = runner.invoke(
                app,
                ["plugin", "uninstall", "my-plugin", "--force"],
                env=env,
            )
    assert result.exit_code == 0
    assert "my-plugin" in result.output


def test_plugin_enable_preview_error(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """enable raises BadParameter on preview PluginError (lines 284-285)."""
    result = runner.invoke(
        app, ["plugin", "enable", "nonexistent-plugin", "--force"], env=machine_env
    )
    assert result.exit_code != 0


def test_plugin_enable_data_error(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """enable_plugin_data raises BadParameter (lines 295-296)."""
    from orcheo.plugins.manager import PluginError

    mock_impact = MagicMock()
    mock_impact.prompt_required = False
    mock_impact.activation_mode = "silent_hot_reload"
    mock_preview = {"name": "my-plugin", "impact": mock_impact}

    with patch(
        "orcheo_sdk.cli.plugin.preview_enable_plugin_data",
        return_value=mock_preview,
    ):
        with patch(
            "orcheo_sdk.cli.plugin.enable_plugin_data",
            side_effect=PluginError("enable failed"),
        ):
            result = runner.invoke(
                app,
                ["plugin", "enable", "my-plugin", "--force"],
                env=machine_env,
            )
    assert result.exit_code != 0


def test_plugin_enable_machine_mode_output(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """Enable in machine mode prints JSON (lines 299-300)."""
    mock_impact = MagicMock()
    mock_impact.prompt_required = False
    mock_impact.activation_mode = "silent_hot_reload"
    mock_preview = {"name": "my-plugin", "impact": mock_impact}
    mock_payload = {"name": "my-plugin", "impact": mock_impact}

    with patch(
        "orcheo_sdk.cli.plugin.preview_enable_plugin_data",
        return_value=mock_preview,
    ):
        with patch(
            "orcheo_sdk.cli.plugin.enable_plugin_data",
            return_value=mock_payload,
        ):
            result = runner.invoke(
                app,
                ["plugin", "enable", "my-plugin", "--force"],
                env=machine_env,
            )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["name"] == "my-plugin"


def test_plugin_disable_preview_error(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """disable raises BadParameter on preview PluginError (lines 318-319)."""
    result = runner.invoke(
        app, ["plugin", "disable", "nonexistent-plugin", "--force"], env=machine_env
    )
    assert result.exit_code != 0


def test_plugin_disable_data_error(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """disable_plugin_data raises BadParameter (lines 329-330)."""
    from orcheo.plugins.manager import PluginError

    mock_impact = MagicMock()
    mock_impact.prompt_required = False
    mock_impact.activation_mode = "silent_hot_reload"
    mock_preview = {"name": "my-plugin", "impact": mock_impact}

    with patch(
        "orcheo_sdk.cli.plugin.preview_disable_plugin_data",
        return_value=mock_preview,
    ):
        with patch(
            "orcheo_sdk.cli.plugin.disable_plugin_data",
            side_effect=PluginError("disable failed"),
        ):
            result = runner.invoke(
                app,
                ["plugin", "disable", "my-plugin", "--force"],
                env=machine_env,
            )
    assert result.exit_code != 0


def test_plugin_disable_machine_mode_output(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """Disable in machine mode prints JSON (lines 333-334)."""
    mock_impact = MagicMock()
    mock_impact.prompt_required = False
    mock_impact.activation_mode = "silent_hot_reload"
    mock_preview = {"name": "my-plugin", "impact": mock_impact}
    mock_payload = {"name": "my-plugin", "impact": mock_impact}

    with patch(
        "orcheo_sdk.cli.plugin.preview_disable_plugin_data",
        return_value=mock_preview,
    ):
        with patch(
            "orcheo_sdk.cli.plugin.disable_plugin_data",
            return_value=mock_payload,
        ):
            result = runner.invoke(
                app,
                ["plugin", "disable", "my-plugin", "--force"],
                env=machine_env,
            )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["name"] == "my-plugin"


def test_plugin_doctor_human_mode_with_errors(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Doctor in human mode renders a table and exits 1 on errors (lines 348-360)."""
    mock_payload = {
        "has_errors": True,
        "checks": [
            {
                "name": "some-check",
                "severity": "ERROR",
                "ok": False,
                "message": "Something failed",
            }
        ],
    }
    with patch("orcheo_sdk.cli.plugin.doctor_plugins_data", return_value=mock_payload):
        result = runner.invoke(app, ["plugin", "doctor"], env=env)
    assert result.exit_code == 1
    assert "Plugin Doctor" in result.output


def test_plugin_doctor_human_mode_no_errors(
    runner: CliRunner, env: dict[str, str]
) -> None:
    """Doctor in human mode exits 0 when no errors (line 358 False branch)."""
    mock_payload = {
        "has_errors": False,
        "checks": [
            {
                "name": "some-check",
                "severity": "INFO",
                "ok": True,
                "message": "All good",
            }
        ],
    }
    with patch("orcheo_sdk.cli.plugin.doctor_plugins_data", return_value=mock_payload):
        result = runner.invoke(app, ["plugin", "doctor"], env=env)
    assert result.exit_code == 0
    assert "Plugin Doctor" in result.output


def test_plugin_doctor_machine_mode_no_errors(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """Doctor in machine mode exits 0 and returns when no errors (line 348)."""
    mock_payload = {
        "has_errors": False,
        "checks": [
            {
                "name": "some-check",
                "severity": "INFO",
                "ok": True,
                "message": "All good",
            }
        ],
    }
    with patch("orcheo_sdk.cli.plugin.doctor_plugins_data", return_value=mock_payload):
        result = runner.invoke(app, ["plugin", "doctor"], env=machine_env)
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["has_errors"] is False


def test_maybe_confirm_machine_mode_prompt_required_raises(
    runner: CliRunner, machine_env: dict[str, str]
) -> None:
    """_maybe_confirm raises BadParameter in machine mode when prompt is needed."""
    mock_impact = MagicMock()
    mock_impact.prompt_required = True
    mock_impact.activation_mode = "requires_restart"
    mock_preview = {"name": "my-plugin", "impact": mock_impact}

    with patch(
        "orcheo_sdk.cli.plugin.preview_update_plugin_data",
        return_value=mock_preview,
    ):
        # No --force in machine mode with prompt_required=True → BadParameter
        result = runner.invoke(
            app,
            ["plugin", "update", "my-plugin"],
            env=machine_env,
        )
    assert result.exit_code != 0
