"""Data models for the Agent Skills subsystem."""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(slots=True)
class SkillMetadata:
    """Parsed metadata from a SKILL.md frontmatter.

    Attributes:
        name: Skill identifier (1-64 chars, lowercase alphanumeric + hyphens).
        description: What the skill does and when to use it (1-1024 chars).
        license: Optional license name or reference.
        compatibility: Optional environment requirements (max 500 chars).
        metadata: Optional arbitrary key-value pairs.
        allowed_tools: Optional space-delimited pre-approved tools.
    """

    name: str
    description: str
    license: str | None = None
    compatibility: str | None = None
    metadata: dict[str, str] | None = None
    allowed_tools: str | None = None


@dataclass(slots=True)
class SkillRecord:
    """Installed skill state persisted in ``skills.toml``.

    Attributes:
        name: Skill name (matches directory name).
        source: Original install path or URL.
        installed_at: ISO 8601 timestamp of installation.
        description: Skill description from SKILL.md.
    """

    name: str
    source: str
    installed_at: str
    description: str


@dataclass(slots=True)
class SkillValidationError:
    """A single validation error found in a SKILL.md file.

    Attributes:
        field: The field name that failed validation.
        message: Human-readable error description.
    """

    field: str
    message: str


@dataclass(slots=True)
class SkillValidationResult:
    """Result of validating a SKILL.md file.

    Attributes:
        valid: Whether the skill passed all validation checks.
        errors: List of validation errors found.
        skill_metadata: Parsed metadata when valid, None otherwise.
    """

    valid: bool
    errors: list[SkillValidationError] = field(default_factory=list)
    skill_metadata: SkillMetadata | None = None


__all__ = [
    "SkillMetadata",
    "SkillRecord",
    "SkillValidationError",
    "SkillValidationResult",
]
