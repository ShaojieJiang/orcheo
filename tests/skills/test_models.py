"""Tests for Agent Skills data models."""

from orcheo.skills.models import (
    SkillMetadata,
    SkillRecord,
    SkillValidationError,
    SkillValidationResult,
)


def test_skill_metadata_required_fields() -> None:
    """SkillMetadata can be created with required fields only."""
    meta = SkillMetadata(name="my-skill", description="Does things.")
    assert meta.name == "my-skill"
    assert meta.description == "Does things."
    assert meta.license is None
    assert meta.compatibility is None
    assert meta.metadata is None
    assert meta.allowed_tools is None


def test_skill_metadata_all_fields() -> None:
    """SkillMetadata supports all optional fields."""
    meta = SkillMetadata(
        name="pdf-processing",
        description="Process PDFs.",
        license="Apache-2.0",
        compatibility="Requires Python 3.12+",
        metadata={"author": "org", "version": "1.0"},
        allowed_tools="Bash(git:*) Read",
    )
    assert meta.license == "Apache-2.0"
    assert meta.compatibility == "Requires Python 3.12+"
    assert meta.metadata == {"author": "org", "version": "1.0"}
    assert meta.allowed_tools == "Bash(git:*) Read"


def test_skill_record() -> None:
    """SkillRecord stores installation state."""
    record = SkillRecord(
        name="my-skill",
        source="./skills/my-skill",
        installed_at="2026-03-21T10:00:00+00:00",
        description="A skill.",
    )
    assert record.name == "my-skill"
    assert record.source == "./skills/my-skill"
    assert record.installed_at == "2026-03-21T10:00:00+00:00"
    assert record.description == "A skill."


def test_skill_validation_error() -> None:
    """SkillValidationError stores field and message."""
    err = SkillValidationError(field="name", message="name is required.")
    assert err.field == "name"
    assert err.message == "name is required."


def test_skill_validation_result_valid() -> None:
    """SkillValidationResult with valid=True."""
    meta = SkillMetadata(name="x", description="d")
    result = SkillValidationResult(valid=True, skill_metadata=meta)
    assert result.valid is True
    assert result.skill_metadata is meta
    assert result.errors == []


def test_skill_validation_result_invalid() -> None:
    """SkillValidationResult with errors."""
    err = SkillValidationError(field="name", message="bad")
    result = SkillValidationResult(valid=False, errors=[err])
    assert result.valid is False
    assert len(result.errors) == 1
    assert result.skill_metadata is None
