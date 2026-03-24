"""Install and manage the official Orcheo skill for external agents."""

from __future__ import annotations
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import httpx
from orcheo.skills.manager import SkillError, SkillManager


OFFICIAL_ORCHEO_SKILL_NAME = "orcheo"
OFFICIAL_ORCHEO_SKILL_REPOSITORY = "https://github.com/AI-Colleagues/orcheo-skill"
OFFICIAL_ORCHEO_SKILL_ARCHIVE_URL = (
    f"{OFFICIAL_ORCHEO_SKILL_REPOSITORY}/archive/refs/heads/main.tar.gz"
)


@dataclass(frozen=True, slots=True)
class OrcheoSkillTarget:
    """A supported external-agent installation target."""

    name: str
    path: Path


def _supported_targets() -> dict[str, OrcheoSkillTarget]:
    home = Path.home()
    return {
        "claude": OrcheoSkillTarget(
            name="claude",
            path=home / ".claude" / "skills" / OFFICIAL_ORCHEO_SKILL_NAME,
        ),
        "codex": OrcheoSkillTarget(
            name="codex",
            path=home / ".codex" / "skills" / OFFICIAL_ORCHEO_SKILL_NAME,
        ),
    }


def resolve_orcheo_skill_targets(
    targets: tuple[str, ...] | list[str] | None,
) -> list[OrcheoSkillTarget]:
    """Normalize CLI target selections."""
    supported = _supported_targets()
    requested = list(targets or ["claude", "codex"])
    if not requested:
        requested = ["claude", "codex"]

    if "all" in requested:
        requested = ["claude", "codex"]

    resolved: list[OrcheoSkillTarget] = []
    seen: set[str] = set()
    for target in requested:
        normalized = target.strip().lower()
        if normalized not in supported:
            raise SkillError("Unsupported target. Use one of: claude, codex, all.")
        if normalized in seen:
            continue
        resolved.append(supported[normalized])
        seen.add(normalized)
    return resolved


def _validate_orcheo_skill(source_dir: Path) -> None:
    validation = SkillManager().validate(str(source_dir))
    if not validation.valid or validation.skill_metadata is None:
        messages = "; ".join(
            f"{error.field}: {error.message}" for error in validation.errors
        )
        raise SkillError(f"Official Orcheo skill is invalid: {messages}")
    if validation.skill_metadata.name != OFFICIAL_ORCHEO_SKILL_NAME:
        raise SkillError(
            "Official Orcheo skill has an unexpected name. "
            f"Expected '{OFFICIAL_ORCHEO_SKILL_NAME}'."
        )


def _extract_downloaded_skill(archive_path: Path, destination_root: Path) -> Path:
    with tarfile.open(archive_path, mode="r:gz") as archive:
        archive.extractall(destination_root)

    extracted_dirs = [path for path in destination_root.iterdir() if path.is_dir()]
    if len(extracted_dirs) != 1:
        raise SkillError("Downloaded Orcheo skill archive has an unexpected layout.")

    source_dir = extracted_dirs[0]
    skill_md = source_dir / "SKILL.md"
    if not skill_md.exists():
        raise SkillError("Downloaded Orcheo skill archive is missing SKILL.md.")
    return source_dir


def _resolve_official_orcheo_skill_source(source: str | None = None) -> Path:
    if source:
        source_dir = Path(source).expanduser().resolve()
        if not source_dir.is_dir():
            raise SkillError(f"Orcheo skill source '{source}' is not a directory.")
        _validate_orcheo_skill(source_dir)
        return source_dir

    temp_root = Path(tempfile.mkdtemp(prefix="orcheo-skill-source-"))
    archive_path = temp_root / "orcheo-skill.tar.gz"

    try:
        with httpx.stream(
            "GET",
            OFFICIAL_ORCHEO_SKILL_ARCHIVE_URL,
            follow_redirects=True,
            timeout=60.0,
        ) as response:
            response.raise_for_status()
            with archive_path.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)

        source_dir = _extract_downloaded_skill(archive_path, temp_root)
        _validate_orcheo_skill(source_dir)
        return source_dir
    except httpx.HTTPError as exc:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise SkillError(
            "Failed to download the official Orcheo skill archive."
        ) from exc


def _copy_or_replace_directory(source_dir: Path, destination_dir: Path) -> None:
    destination_dir.parent.mkdir(parents=True, exist_ok=True)
    if destination_dir.exists():
        shutil.rmtree(destination_dir)
    shutil.copytree(source_dir, destination_dir)


def _target_result(
    target: OrcheoSkillTarget,
    *,
    status: str,
    source: str | None = None,
) -> dict[str, str]:
    result = {
        "target": target.name,
        "path": str(target.path),
        "status": status,
    }
    if source is not None:
        result["source"] = source
    return result


def install_orcheo_skill_data(
    *,
    targets: tuple[str, ...] | list[str] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Install the official Orcheo skill for one or more agent targets."""
    resolved_targets = resolve_orcheo_skill_targets(targets)
    source_dir = _resolve_official_orcheo_skill_source(source)
    try:
        source_label = source or OFFICIAL_ORCHEO_SKILL_REPOSITORY
        existing_targets = [
            target.name for target in resolved_targets if target.path.exists()
        ]
        if existing_targets:
            joined_targets = ", ".join(existing_targets)
            raise SkillError(
                "Orcheo skill is already installed for "
                f"{joined_targets}. Use update instead."
            )
        results: list[dict[str, str]] = []
        for target in resolved_targets:
            _copy_or_replace_directory(source_dir, target.path)
            results.append(
                _target_result(
                    target,
                    status="installed",
                    source=source_label,
                )
            )
        return {
            "skill": OFFICIAL_ORCHEO_SKILL_NAME,
            "action": "install",
            "repository": OFFICIAL_ORCHEO_SKILL_REPOSITORY,
            "targets": results,
        }
    finally:
        if source is None:
            shutil.rmtree(source_dir.parent, ignore_errors=True)


def update_orcheo_skill_data(
    *,
    targets: tuple[str, ...] | list[str] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Update the official Orcheo skill for one or more agent targets."""
    resolved_targets = resolve_orcheo_skill_targets(targets)
    source_dir = _resolve_official_orcheo_skill_source(source)
    try:
        source_label = source or OFFICIAL_ORCHEO_SKILL_REPOSITORY
        results: list[dict[str, str]] = []
        for target in resolved_targets:
            status = "updated" if target.path.exists() else "installed"
            _copy_or_replace_directory(source_dir, target.path)
            results.append(
                _target_result(
                    target,
                    status=status,
                    source=source_label,
                )
            )
        return {
            "skill": OFFICIAL_ORCHEO_SKILL_NAME,
            "action": "update",
            "repository": OFFICIAL_ORCHEO_SKILL_REPOSITORY,
            "targets": results,
        }
    finally:
        if source is None:
            shutil.rmtree(source_dir.parent, ignore_errors=True)


def uninstall_orcheo_skill_data(
    *,
    targets: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    """Uninstall the official Orcheo skill for one or more agent targets."""
    resolved_targets = resolve_orcheo_skill_targets(targets)
    results: list[dict[str, str]] = []
    for target in resolved_targets:
        if target.path.exists():
            shutil.rmtree(target.path)
            results.append(_target_result(target, status="uninstalled"))
            continue
        results.append(_target_result(target, status="not_installed"))
    return {
        "skill": OFFICIAL_ORCHEO_SKILL_NAME,
        "action": "uninstall",
        "repository": OFFICIAL_ORCHEO_SKILL_REPOSITORY,
        "targets": results,
    }


__all__ = [
    "OFFICIAL_ORCHEO_SKILL_ARCHIVE_URL",
    "OFFICIAL_ORCHEO_SKILL_NAME",
    "OFFICIAL_ORCHEO_SKILL_REPOSITORY",
    "install_orcheo_skill_data",
    "resolve_orcheo_skill_targets",
    "uninstall_orcheo_skill_data",
    "update_orcheo_skill_data",
]
