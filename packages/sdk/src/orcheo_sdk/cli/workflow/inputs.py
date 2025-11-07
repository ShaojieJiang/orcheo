"""Input and filesystem helpers for workflow commands."""

from __future__ import annotations
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.state import CLIState


def _resolve_run_inputs(
    inputs: str | None,
    inputs_file: str | None,
) -> dict[str, Any]:
    """Resolve workflow run inputs from inline JSON or file."""
    if inputs and inputs_file:
        raise CLIError("Provide either --inputs or --inputs-file, not both.")
    if inputs:
        return dict(_load_inputs_from_string(inputs))
    if inputs_file:
        return dict(_load_inputs_from_path(inputs_file))
    return {}


def _load_inputs_from_string(value: str) -> Mapping[str, Any]:
    """Parse workflow inputs from a JSON string."""
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:  # pragma: no cover - converted to CLIError
        raise CLIError(f"Invalid JSON payload: {exc}") from exc
    if not isinstance(payload, Mapping):
        msg = "Inputs payload must be a JSON object."
        raise CLIError(msg)
    return payload


def _validate_local_path(
    path: str | Path,
    *,
    description: str,
    must_exist: bool = True,
    require_file: bool = True,
) -> Path:
    """Resolve a user-supplied path and guard against traversal attempts."""
    path_obj = Path(path).expanduser()
    try:
        resolved = path_obj.resolve(strict=False)
    except RuntimeError as exc:  # pragma: no cover - defensive guard
        raise CLIError(f"Failed to resolve {description} path '{path}': {exc}") from exc

    if not path_obj.is_absolute():
        cwd = Path.cwd().resolve()
        try:
            resolved.relative_to(cwd)
        except ValueError as exc:
            message = (
                f"{description.capitalize()} path '{path}' "
                "escapes the current working directory."
            )
            raise CLIError(message) from exc

    if must_exist and not resolved.exists():
        raise CLIError(f"{description.capitalize()} file '{path}' does not exist.")
    if must_exist and require_file and resolved.exists() and not resolved.is_file():
        raise CLIError(f"{description.capitalize()} path '{path}' is not a file.")
    if not must_exist:
        parent = resolved.parent
        if not parent.exists():
            raise CLIError(
                f"Directory '{parent}' for {description} path '{path}' does not exist."
            )
        if not parent.is_dir():
            raise CLIError(f"Parent of {description} path '{path}' is not a directory.")
        if require_file and resolved.exists() and not resolved.is_file():
            raise CLIError(f"{description.capitalize()} path '{path}' is not a file.")

    return resolved


def _load_inputs_from_path(path: str) -> Mapping[str, Any]:
    """Load workflow inputs from a JSON file path."""
    path_obj = _validate_local_path(path, description="inputs")
    data = json.loads(path_obj.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise CLIError("Inputs payload must be a JSON object.")
    return data


def _cache_notice(state: CLIState, subject: str, stale: bool) -> None:
    """Display cache usage notice in the console."""
    note = "[yellow]Using cached data[/yellow]"
    if stale:
        note += " (older than TTL)"
    state.console.print(f"{note} for {subject}.")


__all__ = [
    "_resolve_run_inputs",
    "_load_inputs_from_string",
    "_validate_local_path",
    "_load_inputs_from_path",
    "_cache_notice",
]
