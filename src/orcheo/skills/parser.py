"""SKILL.md frontmatter parser and validator.

Implements parsing and validation per the Agent Skills specification:
https://agentskills.io/specification
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Any
import yaml
from orcheo.skills.models import (
    SkillMetadata,
    SkillValidationError,
    SkillValidationResult,
)


_NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
_CONSECUTIVE_HYPHENS = re.compile(r"--")


def _extract_frontmatter(content: str) -> tuple[dict[str, Any] | None, str]:
    """Extract YAML frontmatter from a SKILL.md file.

    Args:
        content: Full file content.

    Returns:
        Tuple of (parsed frontmatter dict or None, body content).
    """
    stripped = content.lstrip()
    if not stripped.startswith("---"):
        return None, content

    end_index = stripped.find("---", 3)
    if end_index == -1:
        return None, content

    frontmatter_text = stripped[3:end_index].strip()
    body = stripped[end_index + 3 :].strip()

    try:
        parsed = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        return None, content

    if not isinstance(parsed, dict):
        return None, content

    return parsed, body


def _validate_name(
    frontmatter: dict[str, Any],
    *,
    directory_name: str | None,
) -> tuple[str, list[SkillValidationError]]:
    """Validate the ``name`` field."""
    errors: list[SkillValidationError] = []
    name = frontmatter.get("name")

    if not isinstance(name, str) or not name:
        errors.append(SkillValidationError(field="name", message="name is required."))
        return "", errors

    if len(name) > 64:
        errors.append(
            SkillValidationError(
                field="name",
                message="name must be at most 64 characters.",
            )
        )
    if not _NAME_PATTERN.match(name):
        errors.append(
            SkillValidationError(
                field="name",
                message=(
                    "name must contain only lowercase letters, numbers, "
                    "and hyphens, and must not start or end with a hyphen."
                ),
            )
        )
    if _CONSECUTIVE_HYPHENS.search(name):
        errors.append(
            SkillValidationError(
                field="name",
                message="name must not contain consecutive hyphens.",
            )
        )
    if directory_name is not None and name != directory_name:
        errors.append(
            SkillValidationError(
                field="name",
                message=(
                    f"name '{name}' must match the parent directory "
                    f"name '{directory_name}'."
                ),
            )
        )
    return name, errors


def _validate_description(
    frontmatter: dict[str, Any],
) -> tuple[str, list[SkillValidationError]]:
    """Validate the ``description`` field."""
    errors: list[SkillValidationError] = []
    description = frontmatter.get("description")

    if not isinstance(description, str) or not description.strip():
        errors.append(
            SkillValidationError(
                field="description", message="description is required."
            )
        )
        return "", errors

    if len(description) > 1024:
        errors.append(
            SkillValidationError(
                field="description",
                message="description must be at most 1024 characters.",
            )
        )
    return description, errors


def _validate_optional_fields(
    frontmatter: dict[str, Any],
) -> tuple[dict[str, Any], list[SkillValidationError]]:
    """Validate optional fields and return their parsed values."""
    errors: list[SkillValidationError] = []
    values: dict[str, Any] = {}

    # license
    license_value = frontmatter.get("license")
    if license_value is not None and not isinstance(license_value, str):
        errors.append(
            SkillValidationError(field="license", message="license must be a string.")
        )
        license_value = None
    values["license"] = license_value

    # compatibility
    compatibility = frontmatter.get("compatibility")
    if compatibility is not None:
        if not isinstance(compatibility, str):
            errors.append(
                SkillValidationError(
                    field="compatibility",
                    message="compatibility must be a string.",
                )
            )
            compatibility = None
        elif len(compatibility) > 500:
            errors.append(
                SkillValidationError(
                    field="compatibility",
                    message="compatibility must be at most 500 characters.",
                )
            )
    values["compatibility"] = compatibility

    # metadata
    metadata_value = frontmatter.get("metadata")
    if metadata_value is not None:
        if not isinstance(metadata_value, dict):
            errors.append(
                SkillValidationError(
                    field="metadata",
                    message="metadata must be a mapping of strings.",
                )
            )
            metadata_value = None
        else:
            for key, value in metadata_value.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    errors.append(
                        SkillValidationError(
                            field="metadata",
                            message="metadata keys and values must be strings.",
                        )
                    )
                    metadata_value = None
                    break
    values["metadata"] = metadata_value

    # allowed-tools
    allowed_tools = frontmatter.get("allowed-tools")
    if allowed_tools is not None and not isinstance(allowed_tools, str):
        errors.append(
            SkillValidationError(
                field="allowed-tools",
                message="allowed-tools must be a string.",
            )
        )
        allowed_tools = None
    values["allowed_tools"] = allowed_tools

    return values, errors


def validate_skill_metadata(
    frontmatter: dict[str, Any],
    *,
    directory_name: str | None = None,
) -> SkillValidationResult:
    """Validate SKILL.md frontmatter per the Agent Skills specification.

    Args:
        frontmatter: Parsed YAML frontmatter dictionary.
        directory_name: If provided, validates that ``name`` matches.

    Returns:
        Validation result with errors and parsed metadata.
    """
    name, name_errors = _validate_name(frontmatter, directory_name=directory_name)
    description, desc_errors = _validate_description(frontmatter)
    optional_values, opt_errors = _validate_optional_fields(frontmatter)

    all_errors = name_errors + desc_errors + opt_errors
    if all_errors:
        return SkillValidationResult(valid=False, errors=all_errors)

    skill_metadata = SkillMetadata(
        name=name,
        description=description,
        license=optional_values["license"],
        compatibility=optional_values["compatibility"],
        metadata=optional_values["metadata"],
        allowed_tools=optional_values["allowed_tools"],
    )
    return SkillValidationResult(valid=True, skill_metadata=skill_metadata)


def parse_skill_md(
    path: Path,
    *,
    directory_name: str | None = None,
) -> SkillValidationResult:
    """Parse and validate a SKILL.md file.

    Args:
        path: Path to the SKILL.md file.
        directory_name: If provided, validates that ``name`` matches.

    Returns:
        Validation result with errors and parsed metadata.
    """
    if not path.exists():
        return SkillValidationResult(
            valid=False,
            errors=[
                SkillValidationError(
                    field="SKILL.md",
                    message=f"SKILL.md not found at {path}.",
                )
            ],
        )

    content = path.read_text(encoding="utf-8")
    frontmatter, _body = _extract_frontmatter(content)

    if frontmatter is None:
        return SkillValidationResult(
            valid=False,
            errors=[
                SkillValidationError(
                    field="frontmatter",
                    message="SKILL.md must contain valid YAML frontmatter.",
                )
            ],
        )

    return validate_skill_metadata(frontmatter, directory_name=directory_name)


__all__ = [
    "parse_skill_md",
    "validate_skill_metadata",
]
