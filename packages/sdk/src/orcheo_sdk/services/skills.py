"""Agent Skills lifecycle service operations."""

from __future__ import annotations
from typing import Any
from orcheo.skills.manager import SkillManager
from orcheo.skills.models import SkillValidationResult


def list_skills_data() -> list[dict[str, Any]]:
    """Return the current skill inventory."""
    return SkillManager().list_skills()


def show_skill_data(name: str) -> dict[str, Any]:
    """Return details for ``name``."""
    return SkillManager().show_skill(name)


def install_skill_data(ref: str) -> dict[str, Any]:
    """Install a skill from ``ref``."""
    return SkillManager().install(ref)


def uninstall_skill_data(name: str) -> dict[str, str]:
    """Remove an installed skill."""
    return SkillManager().uninstall(name)


def validate_skill_data(ref: str) -> SkillValidationResult:
    """Validate a skill directory without installing."""
    return SkillManager().validate(ref)


__all__ = [
    "install_skill_data",
    "list_skills_data",
    "show_skill_data",
    "uninstall_skill_data",
    "validate_skill_data",
]
