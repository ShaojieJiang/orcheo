"""Tests for Agent Skills SKILL.md parser and validator."""

from pathlib import Path
from orcheo.skills.parser import (
    _extract_frontmatter,
    parse_skill_md,
    validate_skill_metadata,
)


# ---------------------------------------------------------------------------
# _extract_frontmatter
# ---------------------------------------------------------------------------


def test_extract_frontmatter_valid() -> None:
    """Extracts YAML frontmatter from content."""
    content = "---\nname: my-skill\ndescription: Does things.\n---\n# Body"
    frontmatter, body = _extract_frontmatter(content)
    assert frontmatter is not None
    assert frontmatter["name"] == "my-skill"
    assert body == "# Body"


def test_extract_frontmatter_no_delimiter() -> None:
    """Returns None when no frontmatter delimiters are present."""
    content = "# Just a markdown file"
    frontmatter, body = _extract_frontmatter(content)
    assert frontmatter is None
    assert body == content


def test_extract_frontmatter_no_closing_delimiter() -> None:
    """Returns None when closing delimiter is missing."""
    content = "---\nname: test\n"
    frontmatter, body = _extract_frontmatter(content)
    assert frontmatter is None


def test_extract_frontmatter_invalid_yaml() -> None:
    """Returns None when YAML is invalid."""
    content = "---\n: invalid: yaml: [[\n---\n"
    frontmatter, body = _extract_frontmatter(content)
    assert frontmatter is None


def test_extract_frontmatter_non_dict_yaml() -> None:
    """Returns None when YAML parses to a non-dict value."""
    content = "---\n- list\n- item\n---\nBody"
    frontmatter, body = _extract_frontmatter(content)
    assert frontmatter is None


def test_extract_frontmatter_with_leading_whitespace() -> None:
    """Leading whitespace before frontmatter is handled."""
    content = "\n  ---\nname: test\n---\nBody"
    frontmatter, body = _extract_frontmatter(content)
    assert frontmatter is not None
    assert frontmatter["name"] == "test"


# ---------------------------------------------------------------------------
# validate_skill_metadata — name
# ---------------------------------------------------------------------------


def test_validate_valid_name() -> None:
    """Valid name passes validation."""
    result = validate_skill_metadata(
        {"name": "pdf-processing", "description": "Process PDFs."}
    )
    assert result.valid is True
    assert result.skill_metadata is not None
    assert result.skill_metadata.name == "pdf-processing"


def test_validate_name_missing() -> None:
    """Missing name fails validation."""
    result = validate_skill_metadata({"description": "Desc."})
    assert result.valid is False
    assert any(e.field == "name" for e in result.errors)


def test_validate_name_empty() -> None:
    """Empty string name fails validation."""
    result = validate_skill_metadata({"name": "", "description": "Desc."})
    assert result.valid is False
    assert any(e.field == "name" for e in result.errors)


def test_validate_name_non_string() -> None:
    """Non-string name fails validation."""
    result = validate_skill_metadata({"name": 123, "description": "Desc."})
    assert result.valid is False
    assert any(e.field == "name" for e in result.errors)


def test_validate_name_too_long() -> None:
    """Name exceeding 64 chars fails validation."""
    result = validate_skill_metadata({"name": "a" * 65, "description": "Desc."})
    assert result.valid is False
    assert any("64" in e.message for e in result.errors)


def test_validate_name_uppercase() -> None:
    """Uppercase letters in name fail validation."""
    result = validate_skill_metadata({"name": "My-Skill", "description": "Desc."})
    assert result.valid is False


def test_validate_name_starts_with_hyphen() -> None:
    """Name starting with hyphen fails validation."""
    result = validate_skill_metadata({"name": "-my-skill", "description": "Desc."})
    assert result.valid is False


def test_validate_name_ends_with_hyphen() -> None:
    """Name ending with hyphen fails validation."""
    result = validate_skill_metadata({"name": "my-skill-", "description": "Desc."})
    assert result.valid is False


def test_validate_name_consecutive_hyphens() -> None:
    """Name with consecutive hyphens fails validation."""
    result = validate_skill_metadata({"name": "my--skill", "description": "Desc."})
    assert result.valid is False
    assert any("consecutive" in e.message for e in result.errors)


def test_validate_name_single_char() -> None:
    """Single character name is valid."""
    result = validate_skill_metadata({"name": "a", "description": "Desc."})
    assert result.valid is True


def test_validate_name_directory_mismatch() -> None:
    """Name not matching directory name fails."""
    result = validate_skill_metadata(
        {"name": "my-skill", "description": "Desc."},
        directory_name="other-skill",
    )
    assert result.valid is False
    assert any("must match" in e.message for e in result.errors)


def test_validate_name_directory_match() -> None:
    """Name matching directory name passes."""
    result = validate_skill_metadata(
        {"name": "my-skill", "description": "Desc."},
        directory_name="my-skill",
    )
    assert result.valid is True


# ---------------------------------------------------------------------------
# validate_skill_metadata — description
# ---------------------------------------------------------------------------


def test_validate_description_missing() -> None:
    """Missing description fails validation."""
    result = validate_skill_metadata({"name": "test"})
    assert result.valid is False
    assert any(e.field == "description" for e in result.errors)


def test_validate_description_empty() -> None:
    """Empty string description fails validation."""
    result = validate_skill_metadata({"name": "test", "description": ""})
    assert result.valid is False


def test_validate_description_whitespace_only() -> None:
    """Whitespace-only description fails validation."""
    result = validate_skill_metadata({"name": "test", "description": "   "})
    assert result.valid is False


def test_validate_description_non_string() -> None:
    """Non-string description fails validation."""
    result = validate_skill_metadata({"name": "test", "description": 42})
    assert result.valid is False


def test_validate_description_too_long() -> None:
    """Description exceeding 1024 chars fails validation."""
    result = validate_skill_metadata({"name": "test", "description": "x" * 1025})
    assert result.valid is False
    assert any("1024" in e.message for e in result.errors)


# ---------------------------------------------------------------------------
# validate_skill_metadata — optional fields
# ---------------------------------------------------------------------------


def test_validate_license_valid() -> None:
    """Valid license passes."""
    result = validate_skill_metadata(
        {"name": "test", "description": "Desc.", "license": "MIT"}
    )
    assert result.valid is True
    assert result.skill_metadata is not None
    assert result.skill_metadata.license == "MIT"


def test_validate_license_non_string() -> None:
    """Non-string license fails."""
    result = validate_skill_metadata(
        {"name": "test", "description": "Desc.", "license": 123}
    )
    assert result.valid is False


def test_validate_compatibility_valid() -> None:
    """Valid compatibility passes."""
    result = validate_skill_metadata(
        {
            "name": "test",
            "description": "Desc.",
            "compatibility": "Requires Python 3.12+",
        }
    )
    assert result.valid is True
    assert result.skill_metadata is not None
    assert result.skill_metadata.compatibility == "Requires Python 3.12+"


def test_validate_compatibility_too_long() -> None:
    """Compatibility exceeding 500 chars fails."""
    result = validate_skill_metadata(
        {
            "name": "test",
            "description": "Desc.",
            "compatibility": "x" * 501,
        }
    )
    assert result.valid is False


def test_validate_compatibility_non_string() -> None:
    """Non-string compatibility fails."""
    result = validate_skill_metadata(
        {"name": "test", "description": "Desc.", "compatibility": 42}
    )
    assert result.valid is False


def test_validate_metadata_valid() -> None:
    """Valid string-to-string metadata passes."""
    result = validate_skill_metadata(
        {
            "name": "test",
            "description": "Desc.",
            "metadata": {"author": "me"},
        }
    )
    assert result.valid is True
    assert result.skill_metadata is not None
    assert result.skill_metadata.metadata == {"author": "me"}


def test_validate_metadata_non_dict() -> None:
    """Non-dict metadata fails."""
    result = validate_skill_metadata(
        {"name": "test", "description": "Desc.", "metadata": "bad"}
    )
    assert result.valid is False


def test_validate_metadata_non_string_values() -> None:
    """Metadata with non-string values fails."""
    result = validate_skill_metadata(
        {
            "name": "test",
            "description": "Desc.",
            "metadata": {"key": 123},
        }
    )
    assert result.valid is False


def test_validate_allowed_tools_valid() -> None:
    """Valid allowed-tools passes."""
    result = validate_skill_metadata(
        {
            "name": "test",
            "description": "Desc.",
            "allowed-tools": "Bash(git:*) Read",
        }
    )
    assert result.valid is True
    assert result.skill_metadata is not None
    assert result.skill_metadata.allowed_tools == "Bash(git:*) Read"


def test_validate_allowed_tools_non_string() -> None:
    """Non-string allowed-tools fails."""
    result = validate_skill_metadata(
        {"name": "test", "description": "Desc.", "allowed-tools": ["Read"]}
    )
    assert result.valid is False


# ---------------------------------------------------------------------------
# parse_skill_md
# ---------------------------------------------------------------------------


def test_parse_skill_md_valid(tmp_path: Path) -> None:
    """Parses a valid SKILL.md file."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("---\nname: my-skill\ndescription: Does things.\n---\n# Body\n")
    result = parse_skill_md(skill_md, directory_name="my-skill")
    assert result.valid is True
    assert result.skill_metadata is not None
    assert result.skill_metadata.name == "my-skill"


def test_parse_skill_md_missing_file(tmp_path: Path) -> None:
    """Returns error when SKILL.md does not exist."""
    result = parse_skill_md(tmp_path / "SKILL.md")
    assert result.valid is False
    assert any("not found" in e.message for e in result.errors)


def test_parse_skill_md_no_frontmatter(tmp_path: Path) -> None:
    """Returns error when SKILL.md has no frontmatter."""
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Just markdown\n")
    result = parse_skill_md(skill_md)
    assert result.valid is False
    assert any("frontmatter" in e.message for e in result.errors)


def test_parse_skill_md_invalid_frontmatter(tmp_path: Path) -> None:
    """Returns error when frontmatter is invalid."""
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("---\nname: test\n---\n")
    result = parse_skill_md(skill_md)
    assert result.valid is False  # missing description
