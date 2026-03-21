"""Skill lifecycle management for Agent Skills."""

from __future__ import annotations
import shutil
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from orcheo.skills.models import SkillRecord, SkillValidationResult
from orcheo.skills.parser import parse_skill_md
from orcheo.skills.paths import get_skills_dir, get_state_file


class SkillError(RuntimeError):
    """Raised when skill lifecycle operations fail."""


def _load_state(state_file: Path) -> list[SkillRecord]:
    """Load skill records from ``skills.toml``."""
    if not state_file.exists():
        return []
    content = state_file.read_text(encoding="utf-8")
    if not content.strip():
        return []
    try:
        data = tomllib.loads(content)
    except Exception:
        return []

    records: list[SkillRecord] = []
    for entry in data.get("skills", []):
        if not isinstance(entry, dict):  # pragma: no branch
            continue
        name = entry.get("name", "")
        source = entry.get("source", "")
        installed_at = entry.get("installed_at", "")
        description = entry.get("description", "")
        if isinstance(name, str) and name:
            records.append(
                SkillRecord(
                    name=name,
                    source=str(source),
                    installed_at=str(installed_at),
                    description=str(description),
                )
            )
    return records


def _save_state(state_file: Path, records: list[SkillRecord]) -> None:
    """Write skill records to ``skills.toml``."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for record in sorted(records, key=lambda r: r.name.lower()):
        lines.append("[[skills]]")
        lines.append(f'name = "{record.name}"')
        lines.append(f'source = "{record.source}"')
        lines.append(f'installed_at = "{record.installed_at}"')
        lines.append(f'description = "{_escape_toml_string(record.description)}"')
        lines.append("")
    state_file.write_text("\n".join(lines), encoding="utf-8")


def _escape_toml_string(value: str) -> str:
    """Escape a string for safe inclusion in a TOML double-quoted value."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _list_skill_files(skill_dir: Path) -> list[str]:
    """Return relative file paths within a skill directory."""
    files: list[str] = []
    for path in sorted(skill_dir.rglob("*")):
        if path.is_file():
            files.append(str(path.relative_to(skill_dir)))
    return files


class SkillManager:
    """High-level interface for CLI-driven skill lifecycle operations."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        """Initialize the manager with explicit or default skills directory."""
        self.skills_dir = skills_dir or get_skills_dir()
        self.state_file = get_state_file(self.skills_dir)

    def list_skills(self) -> list[dict[str, Any]]:
        """Return all installed skills with their metadata."""
        records = _load_state(self.state_file)
        rows: list[dict[str, Any]] = []
        for record in sorted(records, key=lambda r: r.name.lower()):
            skill_dir = self.skills_dir / record.name
            status = "installed" if skill_dir.exists() else "missing"
            rows.append(
                {
                    "name": record.name,
                    "description": record.description,
                    "source": record.source,
                    "installed_at": record.installed_at,
                    "status": status,
                }
            )
        return rows

    def show_skill(self, name: str) -> dict[str, Any]:
        """Return detailed information about an installed skill."""
        records = {r.name: r for r in _load_state(self.state_file)}
        if name not in records:
            raise SkillError(f"Skill '{name}' is not installed.")

        record = records[name]
        skill_dir = self.skills_dir / name
        skill_md = skill_dir / "SKILL.md"

        result: dict[str, Any] = {
            "name": record.name,
            "description": record.description,
            "source": record.source,
            "installed_at": record.installed_at,
            "status": "installed" if skill_dir.exists() else "missing",
            "license": None,
            "compatibility": None,
            "metadata": None,
            "allowed_tools": None,
            "files": [],
        }

        if skill_md.exists():
            validation = parse_skill_md(skill_md, directory_name=name)
            if validation.valid and validation.skill_metadata is not None:
                meta = validation.skill_metadata
                result["license"] = meta.license
                result["compatibility"] = meta.compatibility
                result["metadata"] = meta.metadata
                result["allowed_tools"] = meta.allowed_tools

        if skill_dir.exists():
            result["files"] = _list_skill_files(skill_dir)

        return result

    def install(self, ref: str) -> dict[str, Any]:
        """Install a skill from a local directory path.

        Args:
            ref: Path to the skill directory containing a SKILL.md file.

        Returns:
            Installed skill metadata.

        Raises:
            SkillError: If the path is invalid, SKILL.md is missing or
                invalid, or a skill with the same name is already installed.
        """
        source_path = Path(ref).expanduser().resolve()

        if not source_path.is_dir():
            raise SkillError(f"Path '{ref}' is not a directory.")

        skill_md = source_path / "SKILL.md"
        validation = parse_skill_md(skill_md, directory_name=source_path.name)

        if not validation.valid:
            messages = "; ".join(
                f"{err.field}: {err.message}" for err in validation.errors
            )
            raise SkillError(f"Skill validation failed: {messages}")

        assert validation.skill_metadata is not None
        skill_name = validation.skill_metadata.name

        records = _load_state(self.state_file)
        existing_names = {r.name for r in records}
        if skill_name in existing_names:
            raise SkillError(
                f"Skill '{skill_name}' is already installed. Uninstall it first."
            )

        target_dir = self.skills_dir / skill_name
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(source_path, target_dir)

        now = datetime.now(UTC).isoformat()
        record = SkillRecord(
            name=skill_name,
            source=ref,
            installed_at=now,
            description=validation.skill_metadata.description,
        )
        records.append(record)
        _save_state(self.state_file, records)

        return self.show_skill(skill_name)

    def uninstall(self, name: str) -> dict[str, str]:
        """Remove an installed skill.

        Args:
            name: Skill name to uninstall.

        Returns:
            Confirmation dict with the removed skill name.

        Raises:
            SkillError: If the skill is not installed.
        """
        records = _load_state(self.state_file)
        if not any(r.name == name for r in records):
            raise SkillError(f"Skill '{name}' is not installed.")

        skill_dir = self.skills_dir / name
        if skill_dir.exists():
            shutil.rmtree(skill_dir)

        updated_records = [r for r in records if r.name != name]
        _save_state(self.state_file, updated_records)

        return {"name": name, "status": "uninstalled"}

    def get_installed_skill_paths(self) -> list[str]:
        """Return absolute paths to all installed skill directories.

        Scans the skills directory for subdirectories that correspond to
        installed skill records. Directories without a matching state
        record are ignored.

        Returns:
            List of absolute path strings for installed skill directories.
        """
        records = _load_state(self.state_file)
        paths: list[str] = []
        for record in sorted(records, key=lambda r: r.name.lower()):
            skill_dir = self.skills_dir / record.name
            if skill_dir.is_dir():
                paths.append(str(skill_dir))
        return paths

    def validate(self, ref: str) -> SkillValidationResult:
        """Validate a skill directory without installing.

        Args:
            ref: Path to the skill directory containing a SKILL.md file.

        Returns:
            Validation result with errors and parsed metadata.
        """
        source_path = Path(ref).expanduser().resolve()

        if not source_path.is_dir():
            raise SkillError(f"Path '{ref}' is not a directory.")

        skill_md = source_path / "SKILL.md"
        return parse_skill_md(skill_md, directory_name=source_path.name)


__all__ = ["SkillError", "SkillManager"]
