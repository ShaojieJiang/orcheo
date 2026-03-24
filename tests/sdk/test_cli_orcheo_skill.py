"""Tests for the standalone ``orcheo-skill`` CLI."""

from __future__ import annotations
import json
from unittest.mock import patch
import pytest
from typer.testing import CliRunner
from orcheo.skills.manager import SkillError
from orcheo_sdk.cli.orcheo_skill import orcheo_skill_app, run


runner = CliRunner()


def test_orcheo_skill_install_outputs_json() -> None:
    payload = {
        "skill": "orcheo",
        "action": "install",
        "targets": [{"target": "claude", "status": "installed", "path": "/tmp/a"}],
    }
    with patch(
        "orcheo_sdk.cli.orcheo_skill.install_orcheo_skill_data",
        return_value=payload,
    ) as mocked_install:
        result = runner.invoke(orcheo_skill_app, ["install", "--target", "claude"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == payload
    mocked_install.assert_called_once()
    assert list(mocked_install.call_args.kwargs["targets"]) == ["claude"]
    assert mocked_install.call_args.kwargs["source"] is None


def test_orcheo_skill_update_human_renders_table() -> None:
    payload = {
        "skill": "orcheo",
        "action": "update",
        "targets": [
            {
                "target": "codex",
                "status": "updated",
                "path": "/tmp/codex",
                "source": "https://github.com/AI-Colleagues/orcheo-skill",
            }
        ],
    }
    with patch(
        "orcheo_sdk.cli.orcheo_skill.update_orcheo_skill_data",
        return_value=payload,
    ):
        result = runner.invoke(
            orcheo_skill_app,
            ["update", "--target", "codex", "--human"],
        )

    assert result.exit_code == 0
    assert "Targets" in result.stdout
    assert "codex" in result.stdout
    assert "updated" in result.stdout


def test_orcheo_skill_uninstall_reports_errors() -> None:
    with patch(
        "orcheo_sdk.cli.orcheo_skill.uninstall_orcheo_skill_data",
        side_effect=SkillError("boom"),
    ):
        result = runner.invoke(orcheo_skill_app, ["uninstall"])

    assert result.exit_code != 0


def test_orcheo_skill_install_propagates_skill_error() -> None:
    """SkillError during install is converted to BadParameter (lines 79-80)."""
    with patch(
        "orcheo_sdk.cli.orcheo_skill.install_orcheo_skill_data",
        side_effect=SkillError("install failed"),
    ):
        result = runner.invoke(orcheo_skill_app, ["install"])

    assert result.exit_code != 0


def test_orcheo_skill_update_propagates_skill_error() -> None:
    """SkillError during update is converted to BadParameter (lines 96-97)."""
    with patch(
        "orcheo_sdk.cli.orcheo_skill.update_orcheo_skill_data",
        side_effect=SkillError("update failed"),
    ):
        result = runner.invoke(orcheo_skill_app, ["update"])

    assert result.exit_code != 0


def test_orcheo_skill_uninstall_outputs_json_on_success() -> None:
    """Successful uninstall renders JSON output (line 114)."""
    payload = {
        "skill": "orcheo",
        "action": "uninstall",
        "targets": [{"target": "claude", "status": "uninstalled", "path": "/tmp/a"}],
    }
    with patch(
        "orcheo_sdk.cli.orcheo_skill.uninstall_orcheo_skill_data",
        return_value=payload,
    ):
        result = runner.invoke(orcheo_skill_app, ["uninstall"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == payload


def test_render_result_human_skips_table_for_non_list_targets() -> None:
    """human=True with non-list targets skips render_table (line 48->exit)."""
    payload = {
        "skill": "orcheo",
        "action": "install",
        "targets": "not-a-list",
    }
    with patch(
        "orcheo_sdk.cli.orcheo_skill.install_orcheo_skill_data",
        return_value=payload,
    ):
        result = runner.invoke(orcheo_skill_app, ["install", "--human"])

    assert result.exit_code == 0
    assert "Targets" not in result.stdout


def test_run_invokes_orcheo_skill_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """run() delegates to orcheo_skill_app (line 119)."""
    called: list[bool] = []
    monkeypatch.setattr(
        "orcheo_sdk.cli.orcheo_skill.orcheo_skill_app",
        lambda: called.append(True),
    )
    run()
    assert called
