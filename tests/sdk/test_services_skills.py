"""Tests for skill service operations."""

from __future__ import annotations
from unittest.mock import MagicMock, patch
from orcheo.skills.models import SkillMetadata, SkillValidationResult
from orcheo_sdk.services.skills import (
    install_skill_data,
    list_skills_data,
    show_skill_data,
    uninstall_skill_data,
    validate_skill_data,
)


def test_list_skills_data_delegates_to_manager() -> None:
    """list_skills_data returns SkillManager().list_skills()."""
    expected = [{"name": "my-skill"}]
    mock_manager = MagicMock()
    mock_manager.list_skills.return_value = expected

    with patch("orcheo_sdk.services.skills.SkillManager", return_value=mock_manager):
        result = list_skills_data()

    mock_manager.list_skills.assert_called_once()
    assert result is expected


def test_show_skill_data_delegates_to_manager() -> None:
    """show_skill_data returns SkillManager().show_skill(name)."""
    expected = {"name": "my-skill", "description": "Desc."}
    mock_manager = MagicMock()
    mock_manager.show_skill.return_value = expected

    with patch("orcheo_sdk.services.skills.SkillManager", return_value=mock_manager):
        result = show_skill_data("my-skill")

    mock_manager.show_skill.assert_called_once_with("my-skill")
    assert result is expected


def test_install_skill_data_delegates_to_manager() -> None:
    """install_skill_data returns SkillManager().install(ref)."""
    expected = {"name": "my-skill"}
    mock_manager = MagicMock()
    mock_manager.install.return_value = expected

    with patch("orcheo_sdk.services.skills.SkillManager", return_value=mock_manager):
        result = install_skill_data("/path/to/skill")

    mock_manager.install.assert_called_once_with("/path/to/skill")
    assert result is expected


def test_uninstall_skill_data_delegates_to_manager() -> None:
    """uninstall_skill_data returns SkillManager().uninstall(name)."""
    expected = {"name": "my-skill", "status": "uninstalled"}
    mock_manager = MagicMock()
    mock_manager.uninstall.return_value = expected

    with patch("orcheo_sdk.services.skills.SkillManager", return_value=mock_manager):
        result = uninstall_skill_data("my-skill")

    mock_manager.uninstall.assert_called_once_with("my-skill")
    assert result is expected


def test_validate_skill_data_delegates_to_manager() -> None:
    """validate_skill_data returns SkillManager().validate(ref)."""
    expected = SkillValidationResult(
        valid=True,
        skill_metadata=SkillMetadata(name="my-skill", description="Desc."),
    )
    mock_manager = MagicMock()
    mock_manager.validate.return_value = expected

    with patch("orcheo_sdk.services.skills.SkillManager", return_value=mock_manager):
        result = validate_skill_data("/path/to/skill")

    mock_manager.validate.assert_called_once_with("/path/to/skill")
    assert result is expected
