"""Tests for agent skills CLI commands."""

from __future__ import annotations
from unittest.mock import MagicMock, patch
from rich.console import Console
from typer.testing import CliRunner
from orcheo.skills.manager import SkillError
from orcheo.skills.models import (
    SkillMetadata,
    SkillValidationError,
    SkillValidationResult,
)
from orcheo_sdk.cli.main import app
from orcheo_sdk.cli.state import CLIState


runner = CliRunner()


def _make_cli_state(*, human: bool) -> CLIState:
    return CLIState(
        settings=MagicMock(),
        client=MagicMock(),
        cache=MagicMock(),
        console=Console(record=True),
        human=human,
    )


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_skills_json() -> None:
    """List skills outputs JSON when not human."""
    rows = [
        {
            "name": "my-skill",
            "description": "A skill.",
            "source": "./path",
            "installed_at": "2026-03-21",
            "status": "installed",
        }
    ]
    with patch("orcheo_sdk.cli.skill.list_skills_data", return_value=rows):
        result = runner.invoke(app, ["skill", "list"])
    assert result.exit_code == 0
    assert "my-skill" in result.output


def test_list_skills_human() -> None:
    """List skills renders a table when human."""
    rows = [
        {
            "name": "test-skill",
            "description": "Test.",
            "source": "./src",
            "installed_at": "2026-03-21",
            "status": "installed",
        }
    ]
    with patch("orcheo_sdk.cli.skill.list_skills_data", return_value=rows):
        result = runner.invoke(app, ["--human", "skill", "list"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


def test_show_skill_json() -> None:
    """Show skill outputs JSON when not human."""
    payload = {"name": "my-skill", "description": "Desc."}
    with patch("orcheo_sdk.cli.skill.show_skill_data", return_value=payload):
        result = runner.invoke(app, ["skill", "show", "my-skill"])
    assert result.exit_code == 0
    assert "my-skill" in result.output


def test_show_skill_human() -> None:
    """Show skill renders rich panel when human."""
    payload = {"name": "my-skill", "description": "Desc."}
    with patch("orcheo_sdk.cli.skill.show_skill_data", return_value=payload):
        result = runner.invoke(app, ["--human", "skill", "show", "my-skill"])
    assert result.exit_code == 0


def test_show_skill_not_found() -> None:
    """Show skill raises error for unknown skill."""
    with patch(
        "orcheo_sdk.cli.skill.show_skill_data",
        side_effect=SkillError("Skill 'foo' is not installed."),
    ):
        result = runner.invoke(app, ["skill", "show", "foo"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


def test_install_skill_json() -> None:
    """Install skill outputs JSON when not human."""
    payload = {"name": "my-skill", "description": "Desc."}
    with patch("orcheo_sdk.cli.skill.install_skill_data", return_value=payload):
        result = runner.invoke(app, ["skill", "install", "./path"])
    assert result.exit_code == 0
    assert "my-skill" in result.output


def test_install_skill_human() -> None:
    """Install skill renders rich panel when human."""
    payload = {"name": "my-skill", "description": "Desc."}
    with patch("orcheo_sdk.cli.skill.install_skill_data", return_value=payload):
        result = runner.invoke(app, ["--human", "skill", "install", "./path"])
    assert result.exit_code == 0


def test_install_skill_error() -> None:
    """Install skill raises error for invalid ref."""
    with patch(
        "orcheo_sdk.cli.skill.install_skill_data",
        side_effect=SkillError("not a directory"),
    ):
        result = runner.invoke(app, ["skill", "install", "/bad"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------


def test_uninstall_skill_json() -> None:
    """Uninstall skill outputs JSON when not human."""
    payload = {"name": "my-skill", "status": "uninstalled"}
    with patch("orcheo_sdk.cli.skill.uninstall_skill_data", return_value=payload):
        result = runner.invoke(app, ["skill", "uninstall", "my-skill"])
    assert result.exit_code == 0


def test_uninstall_skill_human() -> None:
    """Uninstall skill prints confirmation when human."""
    payload = {"name": "my-skill", "status": "uninstalled"}
    with patch("orcheo_sdk.cli.skill.uninstall_skill_data", return_value=payload):
        result = runner.invoke(app, ["--human", "skill", "uninstall", "my-skill"])
    assert result.exit_code == 0


def test_uninstall_skill_error() -> None:
    """Uninstall raises error for unknown skill."""
    with patch(
        "orcheo_sdk.cli.skill.uninstall_skill_data",
        side_effect=SkillError("not installed"),
    ):
        result = runner.invoke(app, ["skill", "uninstall", "foo"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_validate_skill_valid_json() -> None:
    """Validate valid skill outputs JSON when not human."""
    validation = SkillValidationResult(
        valid=True,
        skill_metadata=SkillMetadata(name="my-skill", description="Desc."),
    )
    with patch("orcheo_sdk.cli.skill.validate_skill_data", return_value=validation):
        result = runner.invoke(app, ["skill", "validate", "./path"])
    assert result.exit_code == 0
    assert "my-skill" in result.output


def test_validate_skill_valid_human() -> None:
    """Validate valid skill prints name when human."""
    validation = SkillValidationResult(
        valid=True,
        skill_metadata=SkillMetadata(name="my-skill", description="Desc."),
    )
    with patch("orcheo_sdk.cli.skill.validate_skill_data", return_value=validation):
        result = runner.invoke(app, ["--human", "skill", "validate", "./path"])
    assert result.exit_code == 0


def test_validate_skill_invalid_json() -> None:
    """Validate invalid skill outputs errors and exits with code 1."""
    validation = SkillValidationResult(
        valid=False,
        errors=[SkillValidationError(field="name", message="name is required.")],
    )
    with patch("orcheo_sdk.cli.skill.validate_skill_data", return_value=validation):
        result = runner.invoke(app, ["skill", "validate", "./path"])
    assert result.exit_code == 1


def test_validate_skill_invalid_human() -> None:
    """Validate invalid skill prints errors when human."""
    validation = SkillValidationResult(
        valid=False,
        errors=[SkillValidationError(field="name", message="name is required.")],
    )
    with patch("orcheo_sdk.cli.skill.validate_skill_data", return_value=validation):
        result = runner.invoke(app, ["--human", "skill", "validate", "./path"])
    assert result.exit_code == 1


def test_validate_skill_error() -> None:
    """Validate raises error for non-directory path."""
    with patch(
        "orcheo_sdk.cli.skill.validate_skill_data",
        side_effect=SkillError("not a directory"),
    ):
        result = runner.invoke(app, ["skill", "validate", "/bad"])
    assert result.exit_code != 0
