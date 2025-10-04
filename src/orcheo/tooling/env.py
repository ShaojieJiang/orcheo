"""Utilities for preparing local development environments."""

from __future__ import annotations
import argparse
from pathlib import Path
from typing import Final


ENV_FILENAME: Final[str] = ".env"
ENV_EXAMPLE_FILENAME: Final[str] = ".env.example"


class SeedEnvError(RuntimeError):
    """Raised when the environment seed process cannot be completed."""


def seed_env_file(
    project_root: Path | None = None,
    *,
    overwrite: bool = False,
) -> Path:
    """Create a local ``.env`` file from ``.env.example``.

    Args:
        project_root: Repository root containing the environment files. When ``None``
            the current working directory is used.
        overwrite: Whether to overwrite an existing ``.env`` file.

    Returns:
        Path to the seeded ``.env`` file.

    Raises:
        FileNotFoundError: If ``.env.example`` is missing.
        SeedEnvError: If the copy fails unexpectedly.
    """
    root = project_root or Path.cwd()
    example_path = root / ENV_EXAMPLE_FILENAME
    if not example_path.exists():
        raise FileNotFoundError(f"Missing {ENV_EXAMPLE_FILENAME} in {root}")

    target_path = root / ENV_FILENAME
    if target_path.exists() and not overwrite:
        return target_path

    try:
        target_path.write_text(example_path.read_text())
    except OSError as exc:  # pragma: no cover - defensive guard
        raise SeedEnvError("Unable to copy environment template") from exc

    _create_state_directories(example_path, root)
    return target_path


def _create_state_directories(example_path: Path, root: Path) -> None:
    """Create directories referenced by seeded environment variables."""
    for value in _extract_path_values(example_path):
        resolved_path = (root / value).expanduser()
        target_directory = (
            resolved_path
            if resolved_path.suffix == "" or resolved_path.is_dir()
            else resolved_path.parent
        )
        if not target_directory.exists():
            target_directory.mkdir(parents=True, exist_ok=True)


def _extract_path_values(example_path: Path) -> set[Path]:
    """Return path-like environment values from ``.env.example``."""
    values: set[Path] = set()
    for raw_line in example_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, raw_value = line.split("=", maxsplit=1)
        if "PATH" not in key and not key.endswith("_DIR"):
            continue
        value = raw_value.strip().strip('"')
        if not value or value.startswith("$"):
            continue
        # Only create directories for relative paths inside the repo
        path_value = Path(value)
        if not path_value.is_absolute():
            values.add(path_value)
    return values


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed a local .env file and create state directories."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing .env file if present.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Optional repository root. Defaults to the current working directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``seed-env`` script."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    seed_env_file(project_root=args.root, overwrite=args.force)
    print("Seeded .env file successfully.")  # noqa: T201 - user-facing output
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
