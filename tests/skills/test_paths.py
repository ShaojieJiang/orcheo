"""Tests for Agent Skills path helpers."""

from pathlib import Path
from orcheo.skills.paths import SKILLS_DIR_ENV, get_skills_dir, get_state_file


def test_get_skills_dir_default() -> None:
    """Default skills directory is ~/.orcheo/skills/."""
    result = get_skills_dir()
    assert result == Path.home() / ".orcheo" / "skills"


def test_get_skills_dir_env_override(monkeypatch: object) -> None:
    """ORCHEO_SKILLS_DIR overrides the default directory."""
    import pytest

    mp = pytest.MonkeyPatch()
    mp.setenv(SKILLS_DIR_ENV, "/tmp/custom-skills")
    try:
        result = get_skills_dir()
        assert result == Path("/tmp/custom-skills")
    finally:
        mp.undo()


def test_get_state_file_default() -> None:
    """State file is skills.toml in the skills directory."""
    result = get_state_file()
    assert result == Path.home() / ".orcheo" / "skills" / "skills.toml"


def test_get_state_file_custom_dir() -> None:
    """State file respects a custom skills directory."""
    custom = Path("/tmp/my-skills")
    result = get_state_file(custom)
    assert result == Path("/tmp/my-skills/skills.toml")


def test_skills_dir_env_constant() -> None:
    """SKILLS_DIR_ENV constant has the expected value."""
    assert SKILLS_DIR_ENV == "ORCHEO_SKILLS_DIR"
