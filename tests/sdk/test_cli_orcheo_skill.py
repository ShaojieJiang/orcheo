"""Tests for the standalone ``orcheo-skill`` CLI."""

from __future__ import annotations
import json
from unittest.mock import patch
from typer.testing import CliRunner
from orcheo.skills.manager import SkillError
from orcheo_sdk.cli.orcheo_skill import orcheo_skill_app


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
