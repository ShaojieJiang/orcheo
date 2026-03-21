"""Filesystem path helpers for the Agent Skills subsystem."""

from __future__ import annotations
import os
from pathlib import Path


SKILLS_DIR_ENV = "ORCHEO_SKILLS_DIR"


def get_skills_dir() -> Path:
    """Return the skills storage directory.

    Respects the ``ORCHEO_SKILLS_DIR`` environment variable when set,
    otherwise defaults to ``~/.orcheo/skills/``.
    """
    override = os.getenv(SKILLS_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".orcheo" / "skills"


def get_state_file(skills_dir: Path | None = None) -> Path:
    """Return the path to the skills state file (``skills.toml``)."""
    return (skills_dir or get_skills_dir()) / "skills.toml"


__all__ = [
    "SKILLS_DIR_ENV",
    "get_skills_dir",
    "get_state_file",
]
