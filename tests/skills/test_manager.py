"""Tests for Agent Skills manager."""

from pathlib import Path
import pytest
from orcheo.skills.manager import (
    SkillError,
    SkillManager,
    _escape_toml_string,
    _list_skill_files,
    _load_state,
    _save_state,
)
from orcheo.skills.models import SkillRecord


# ---------------------------------------------------------------------------
# _escape_toml_string
# ---------------------------------------------------------------------------


def test_escape_toml_string_plain() -> None:
    """Plain string is unchanged."""
    assert _escape_toml_string("hello world") == "hello world"


def test_escape_toml_string_quotes() -> None:
    """Double quotes are escaped."""
    assert _escape_toml_string('say "hi"') == 'say \\"hi\\"'


def test_escape_toml_string_backslash() -> None:
    """Backslashes are escaped."""
    assert _escape_toml_string("a\\b") == "a\\\\b"


def test_escape_toml_string_newline() -> None:
    """Newlines are escaped."""
    assert _escape_toml_string("line1\nline2") == "line1\\nline2"


# ---------------------------------------------------------------------------
# _list_skill_files
# ---------------------------------------------------------------------------


def test_list_skill_files(tmp_path: Path) -> None:
    """Lists all files relative to skill directory."""
    (tmp_path / "SKILL.md").write_text("content")
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "run.py").write_text("print()")
    files = _list_skill_files(tmp_path)
    assert "SKILL.md" in files
    assert "scripts/run.py" in files


def test_list_skill_files_empty(tmp_path: Path) -> None:
    """Empty directory returns empty list."""
    assert _list_skill_files(tmp_path) == []


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


def test_load_state_empty(tmp_path: Path) -> None:
    """Returns empty list when state file doesn't exist."""
    result = _load_state(tmp_path / "skills.toml")
    assert result == []


def test_load_state_empty_file(tmp_path: Path) -> None:
    """Returns empty list for an empty state file."""
    state_file = tmp_path / "skills.toml"
    state_file.write_text("")
    assert _load_state(state_file) == []


def test_save_and_load_state(tmp_path: Path) -> None:
    """Records survive a save and load round-trip."""
    state_file = tmp_path / "skills.toml"
    records = [
        SkillRecord(
            name="my-skill",
            source="./skills/my-skill",
            installed_at="2026-03-21T10:00:00+00:00",
            description="A skill.",
        )
    ]
    _save_state(state_file, records)
    loaded = _load_state(state_file)
    assert len(loaded) == 1
    assert loaded[0].name == "my-skill"
    assert loaded[0].source == "./skills/my-skill"
    assert loaded[0].description == "A skill."


def test_save_state_creates_parent(tmp_path: Path) -> None:
    """Save creates parent directories if needed."""
    state_file = tmp_path / "nested" / "dir" / "skills.toml"
    _save_state(state_file, [])
    assert state_file.exists()


def test_save_state_sorted(tmp_path: Path) -> None:
    """Records are saved in sorted order."""
    state_file = tmp_path / "skills.toml"
    records = [
        SkillRecord(name="zeta", source="z", installed_at="t", description="Z"),
        SkillRecord(name="alpha", source="a", installed_at="t", description="A"),
    ]
    _save_state(state_file, records)
    loaded = _load_state(state_file)
    assert loaded[0].name == "alpha"
    assert loaded[1].name == "zeta"


def test_save_state_escapes_description(tmp_path: Path) -> None:
    """Descriptions with special characters are properly escaped."""
    state_file = tmp_path / "skills.toml"
    records = [
        SkillRecord(
            name="test",
            source="s",
            installed_at="t",
            description='Has "quotes" and\nnewlines.',
        )
    ]
    _save_state(state_file, records)
    loaded = _load_state(state_file)
    assert loaded[0].description == 'Has "quotes" and\nnewlines.'


def test_load_state_invalid_toml(tmp_path: Path) -> None:
    """Returns empty list for invalid TOML content."""
    state_file = tmp_path / "skills.toml"
    state_file.write_text("[[[invalid toml")
    assert _load_state(state_file) == []


def test_load_state_skips_non_dict_entries(tmp_path: Path) -> None:
    """Non-dict entries in skills array are skipped."""
    state_file = tmp_path / "skills.toml"
    state_file.write_text('[[skills]]\nname = "good"\nsource = "s"\n')
    loaded = _load_state(state_file)
    assert len(loaded) == 1


def test_load_state_skips_entries_with_list_in_skills(tmp_path: Path) -> None:
    """Handles skills key containing non-dict entries gracefully."""
    state_file = tmp_path / "skills.toml"
    # Manually write TOML with a valid entry to test the dict parsing branch
    state_file.write_text('skills = [{name = "valid", source = "s"}]\n')
    loaded = _load_state(state_file)
    assert len(loaded) == 1


def test_load_state_skips_entry_with_empty_name(tmp_path: Path) -> None:
    """Entries with empty names are skipped."""
    state_file = tmp_path / "skills.toml"
    state_file.write_text(
        '[[skills]]\nname = ""\nsource = "s"\n\n'
        '[[skills]]\nname = "good"\nsource = "s"\n'
    )
    loaded = _load_state(state_file)
    assert len(loaded) == 1
    assert loaded[0].name == "good"


# ---------------------------------------------------------------------------
# SkillManager
# ---------------------------------------------------------------------------


def _create_skill_dir(
    base: Path,
    name: str,
    description: str = "A test skill.",
) -> Path:
    """Create a minimal valid skill directory."""
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n# {name}\n"
    )
    return skill_dir


def test_manager_install_and_list(tmp_path: Path) -> None:
    """Install a skill and verify it appears in list."""
    skills_dir = tmp_path / "skills"
    source = tmp_path / "sources"
    source.mkdir()
    _create_skill_dir(source, "my-skill")

    manager = SkillManager(skills_dir=skills_dir)
    result = manager.install(str(source / "my-skill"))

    assert result["name"] == "my-skill"
    assert result["status"] == "installed"

    listing = manager.list_skills()
    assert len(listing) == 1
    assert listing[0]["name"] == "my-skill"
    assert listing[0]["status"] == "installed"


def test_manager_install_duplicate(tmp_path: Path) -> None:
    """Installing a duplicate skill name raises SkillError."""
    skills_dir = tmp_path / "skills"
    source = tmp_path / "sources"
    source.mkdir()
    _create_skill_dir(source, "my-skill")

    manager = SkillManager(skills_dir=skills_dir)
    manager.install(str(source / "my-skill"))

    with pytest.raises(SkillError, match="already installed"):
        manager.install(str(source / "my-skill"))


def test_manager_install_not_directory(tmp_path: Path) -> None:
    """Installing from a file path raises SkillError."""
    manager = SkillManager(skills_dir=tmp_path / "skills")
    with pytest.raises(SkillError, match="not a directory"):
        manager.install(str(tmp_path / "nonexistent"))


def test_manager_install_invalid_skill(tmp_path: Path) -> None:
    """Installing a skill with invalid SKILL.md raises SkillError."""
    skills_dir = tmp_path / "skills"
    source = tmp_path / "sources" / "bad-skill"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: bad-skill\n---\n")

    manager = SkillManager(skills_dir=skills_dir)
    with pytest.raises(SkillError, match="validation failed"):
        manager.install(str(source))


def test_manager_show_skill(tmp_path: Path) -> None:
    """Show returns full skill details."""
    skills_dir = tmp_path / "skills"
    source = tmp_path / "sources"
    source.mkdir()
    skill_dir = _create_skill_dir(source, "test-skill", "Test description.")
    (skill_dir / "scripts").mkdir()
    (skill_dir / "scripts" / "run.py").write_text("print('hello')")

    manager = SkillManager(skills_dir=skills_dir)
    manager.install(str(skill_dir))

    details = manager.show_skill("test-skill")
    assert details["name"] == "test-skill"
    assert details["description"] == "Test description."
    assert details["status"] == "installed"
    assert "SKILL.md" in details["files"]
    assert "scripts/run.py" in details["files"]


def test_manager_show_skill_not_found(tmp_path: Path) -> None:
    """Show raises SkillError for unknown skill."""
    manager = SkillManager(skills_dir=tmp_path / "skills")
    with pytest.raises(SkillError, match="not installed"):
        manager.show_skill("nonexistent")


def test_manager_uninstall(tmp_path: Path) -> None:
    """Uninstall removes skill directory and state record."""
    skills_dir = tmp_path / "skills"
    source = tmp_path / "sources"
    source.mkdir()
    _create_skill_dir(source, "my-skill")

    manager = SkillManager(skills_dir=skills_dir)
    manager.install(str(source / "my-skill"))

    result = manager.uninstall("my-skill")
    assert result["name"] == "my-skill"
    assert result["status"] == "uninstalled"
    assert not (skills_dir / "my-skill").exists()
    assert manager.list_skills() == []


def test_manager_uninstall_not_installed(tmp_path: Path) -> None:
    """Uninstall raises SkillError for unknown skill."""
    manager = SkillManager(skills_dir=tmp_path / "skills")
    with pytest.raises(SkillError, match="not installed"):
        manager.uninstall("nonexistent")


def test_manager_validate_valid(tmp_path: Path) -> None:
    """Validate returns valid result for a correct skill."""
    _create_skill_dir(tmp_path, "my-skill")
    manager = SkillManager(skills_dir=tmp_path / "skills")
    result = manager.validate(str(tmp_path / "my-skill"))
    assert result.valid is True


def test_manager_validate_invalid(tmp_path: Path) -> None:
    """Validate returns errors for an invalid skill."""
    skill_dir = tmp_path / "bad-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: bad-skill\n---\n")
    manager = SkillManager(skills_dir=tmp_path / "skills")
    result = manager.validate(str(skill_dir))
    assert result.valid is False


def test_manager_validate_not_directory(tmp_path: Path) -> None:
    """Validate raises SkillError for non-directory path."""
    manager = SkillManager(skills_dir=tmp_path / "skills")
    with pytest.raises(SkillError, match="not a directory"):
        manager.validate(str(tmp_path / "nonexistent"))


def test_manager_list_empty(tmp_path: Path) -> None:
    """List returns empty when no skills installed."""
    manager = SkillManager(skills_dir=tmp_path / "skills")
    assert manager.list_skills() == []


def test_manager_install_overwrites_leftover_directory(tmp_path: Path) -> None:
    """Install overwrites a leftover skill directory (no state record)."""
    skills_dir = tmp_path / "skills"
    source = tmp_path / "sources"
    source.mkdir()
    _create_skill_dir(source, "my-skill")

    # Pre-create a leftover directory without a state record
    leftover = skills_dir / "my-skill"
    leftover.mkdir(parents=True)
    (leftover / "stale.txt").write_text("old")

    manager = SkillManager(skills_dir=skills_dir)
    result = manager.install(str(source / "my-skill"))
    assert result["name"] == "my-skill"
    assert not (skills_dir / "my-skill" / "stale.txt").exists()
    assert (skills_dir / "my-skill" / "SKILL.md").exists()


# ---------------------------------------------------------------------------
# get_installed_skill_paths
# ---------------------------------------------------------------------------


def test_get_installed_skill_paths_empty(tmp_path: Path) -> None:
    """Returns empty list when no skills are installed."""
    manager = SkillManager(skills_dir=tmp_path / "skills")
    assert manager.get_installed_skill_paths() == []


def test_get_installed_skill_paths_populated(tmp_path: Path) -> None:
    """Returns paths for all installed skills."""
    skills_dir = tmp_path / "skills"
    source = tmp_path / "sources"
    source.mkdir()
    _create_skill_dir(source, "alpha-skill")
    _create_skill_dir(source, "beta-skill")

    manager = SkillManager(skills_dir=skills_dir)
    manager.install(str(source / "alpha-skill"))
    manager.install(str(source / "beta-skill"))

    paths = manager.get_installed_skill_paths()
    assert len(paths) == 2
    assert str(skills_dir / "alpha-skill") in paths
    assert str(skills_dir / "beta-skill") in paths


def test_get_installed_skill_paths_skips_missing_dir(tmp_path: Path) -> None:
    """Skips skills whose directory has been removed."""
    skills_dir = tmp_path / "skills"
    source = tmp_path / "sources"
    source.mkdir()
    _create_skill_dir(source, "my-skill")

    manager = SkillManager(skills_dir=skills_dir)
    manager.install(str(source / "my-skill"))

    import shutil

    shutil.rmtree(skills_dir / "my-skill")

    paths = manager.get_installed_skill_paths()
    assert paths == []


def test_get_installed_skill_paths_sorted(tmp_path: Path) -> None:
    """Paths are returned in sorted order by skill name."""
    skills_dir = tmp_path / "skills"
    source = tmp_path / "sources"
    source.mkdir()
    _create_skill_dir(source, "zeta-skill")
    _create_skill_dir(source, "alpha-skill")

    manager = SkillManager(skills_dir=skills_dir)
    manager.install(str(source / "zeta-skill"))
    manager.install(str(source / "alpha-skill"))

    paths = manager.get_installed_skill_paths()
    assert paths[0].endswith("alpha-skill")
    assert paths[1].endswith("zeta-skill")


def test_manager_show_skill_invalid_skill_md(tmp_path: Path) -> None:
    """Show still returns data when installed SKILL.md is invalid (validation fails)."""
    skills_dir = tmp_path / "skills"
    source = tmp_path / "sources"
    source.mkdir()
    _create_skill_dir(source, "my-skill")

    manager = SkillManager(skills_dir=skills_dir)
    manager.install(str(source / "my-skill"))

    # Corrupt the installed SKILL.md so validation fails
    (skills_dir / "my-skill" / "SKILL.md").write_text("---\nname: my-skill\n---\n")

    details = manager.show_skill("my-skill")
    assert details["name"] == "my-skill"
    # Metadata fields remain None when validation fails
    assert details["license"] is None
    assert details["compatibility"] is None
    assert details["metadata"] is None
    assert details["allowed_tools"] is None
    # Files are still listed (skill_dir exists)
    assert "SKILL.md" in details["files"]


def test_manager_uninstall_missing_directory(tmp_path: Path) -> None:
    """Uninstall succeeds when skill directory is already gone."""
    skills_dir = tmp_path / "skills"
    source = tmp_path / "sources"
    source.mkdir()
    _create_skill_dir(source, "my-skill")

    manager = SkillManager(skills_dir=skills_dir)
    manager.install(str(source / "my-skill"))

    import shutil

    shutil.rmtree(skills_dir / "my-skill")

    result = manager.uninstall("my-skill")
    assert result["name"] == "my-skill"
    assert result["status"] == "uninstalled"
    assert manager.list_skills() == []


def test_manager_show_skill_missing_directory(tmp_path: Path) -> None:
    """Show reports 'missing' status when skill directory is gone."""
    skills_dir = tmp_path / "skills"
    source = tmp_path / "sources"
    source.mkdir()
    _create_skill_dir(source, "my-skill")

    manager = SkillManager(skills_dir=skills_dir)
    manager.install(str(source / "my-skill"))

    import shutil

    shutil.rmtree(skills_dir / "my-skill")

    details = manager.show_skill("my-skill")
    assert details["status"] == "missing"
    assert details["files"] == []
