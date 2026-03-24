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


def _resolve_runnable_config(
    config: str | None,
    config_file: str | None,
) -> dict[str, Any] | None:
    """Resolve a runnable config from inline JSON or file."""
    if not config and not config_file:
        return None
    if config and config_file:
        raise CLIError("Provide either --config or --config-file, not both.")
    if config:
        try:
            payload = json.loads(config)
        except json.JSONDecodeError as exc:  # pragma: no cover - converted to CLIError
            raise CLIError(f"Invalid JSON payload: {exc}") from exc
        if not isinstance(payload, Mapping):
            msg = "Runnable config payload must be a JSON object."
            raise CLIError(msg)
        return dict(payload)
    if config_file:
        path_obj = _validate_local_path(config_file, description="config")
        data = json.loads(path_obj.read_text(encoding="utf-8"))
        if not isinstance(data, Mapping):
            raise CLIError("Runnable config payload must be a JSON object.")
        return dict(data)
    return None  # pragma: no cover - defensive guard


def _normalize_chatkit_prompt_entry(
    entry: object,
    *,
    index: int,
) -> dict[str, Any]:
    """Normalize one ChatKit starter-prompt entry from CLI input."""
    if isinstance(entry, str):
        text = entry.strip()
        if not text:
            raise CLIError(f"ChatKit prompt entry {index} must not be an empty string.")
        return {"label": text, "prompt": text}
    if not isinstance(entry, Mapping):
        raise CLIError(f"ChatKit prompt entry {index} must be a string or JSON object.")

    extra_keys = set(entry) - {"label", "prompt", "icon"}
    if extra_keys:
        keys = ", ".join(sorted(str(key) for key in extra_keys))
        raise CLIError(
            f"ChatKit prompt entry {index} contains unsupported keys: {keys}."
        )

    label = entry.get("label")
    prompt = entry.get("prompt", label)
    icon = entry.get("icon")

    if not isinstance(label, str) or not label.strip():
        raise CLIError(f"ChatKit prompt entry {index} requires a non-empty label.")
    if not isinstance(prompt, str) or not prompt.strip():
        raise CLIError(f"ChatKit prompt entry {index} requires a non-empty prompt.")
    if icon is not None and (not isinstance(icon, str) or not icon.strip()):
        raise CLIError(f"ChatKit prompt entry {index} icon must be a non-empty string.")

    payload: dict[str, Any] = {
        "label": label.strip(),
        "prompt": prompt.strip(),
    }
    if isinstance(icon, str) and icon.strip():
        payload["icon"] = icon.strip()
    return payload


def _resolve_chatkit_start_screen_prompts(
    prompts: str | None,
    prompts_file: str | None,
) -> list[dict[str, Any]] | None:
    """Resolve ChatKit starter prompts from inline JSON or a JSON file."""
    if not prompts and not prompts_file:
        return None
    if prompts and prompts_file:
        raise CLIError(
            "Provide either --chatkit-prompts or --chatkit-prompts-file, not both."
        )

    if prompts:
        try:
            raw_payload = json.loads(prompts)
        except json.JSONDecodeError as exc:  # pragma: no cover - converted to CLIError
            raise CLIError(f"Invalid JSON payload: {exc}") from exc
    else:
        assert prompts_file is not None
        path_obj = _validate_local_path(prompts_file, description="chatkit prompts")
        raw_payload = json.loads(path_obj.read_text(encoding="utf-8"))

    if not isinstance(raw_payload, list):
        raise CLIError("ChatKit prompts payload must be a JSON array.")

    return [
        _normalize_chatkit_prompt_entry(entry, index=index)
        for index, entry in enumerate(raw_payload, start=1)
    ]


def _normalize_chatkit_model_entry(
    entry: object,
    *,
    index: int,
) -> dict[str, Any]:
    """Normalize one ChatKit supported-model entry from CLI input."""
    if isinstance(entry, str):
        model_id = entry.strip()
        if not model_id:
            raise CLIError(f"ChatKit model entry {index} must not be an empty string.")
        return {"id": model_id, "label": model_id}
    if not isinstance(entry, Mapping):
        raise CLIError(f"ChatKit model entry {index} must be a string or JSON object.")

    _validate_chatkit_model_entry_keys(entry, index=index)
    model_id = _required_chatkit_model_string(entry.get("id"), index=index, key="id")
    label = _optional_chatkit_model_string(
        entry.get("label", model_id),
        index=index,
        key="label",
    )
    description = _optional_chatkit_model_string(
        entry.get("description"),
        index=index,
        key="description",
    )
    default = _optional_chatkit_model_bool(
        entry.get("default"),
        index=index,
        key="default",
    )
    disabled = _optional_chatkit_model_bool(
        entry.get("disabled"),
        index=index,
        key="disabled",
    )

    payload: dict[str, Any] = {
        "id": model_id,
        "label": label or model_id,
    }
    if description is not None:
        payload["description"] = description
    if default is not None:
        payload["default"] = default
    if disabled is not None:
        payload["disabled"] = disabled
    return payload


def _validate_chatkit_model_entry_keys(
    entry: Mapping[object, object], *, index: int
) -> None:
    """Reject unsupported keys in a ChatKit supported-model entry."""
    extra_keys = set(entry) - {"id", "label", "description", "default", "disabled"}
    if not extra_keys:
        return
    keys = ", ".join(sorted(str(key) for key in extra_keys))
    raise CLIError(f"ChatKit model entry {index} contains unsupported keys: {keys}.")


def _required_chatkit_model_string(
    value: object,
    *,
    index: int,
    key: str,
) -> str:
    """Return a trimmed required string field for a ChatKit model entry."""
    normalized = _optional_chatkit_model_string(value, index=index, key=key)
    if normalized is None:
        raise CLIError(f"ChatKit model entry {index} requires a non-empty {key}.")
    return normalized


def _optional_chatkit_model_string(
    value: object,
    *,
    index: int,
    key: str,
) -> str | None:
    """Return a trimmed optional string field for a ChatKit model entry."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CLIError(f"ChatKit model entry {index} {key} must be a non-empty string.")
    return value.strip()


def _optional_chatkit_model_bool(
    value: object,
    *,
    index: int,
    key: str,
) -> bool | None:
    """Return an optional boolean field for a ChatKit model entry."""
    if value is None:
        return None
    if not isinstance(value, bool):
        raise CLIError(f"ChatKit model entry {index} {key} must be a boolean.")
    return value


def _resolve_chatkit_supported_models(
    models: str | None,
    models_file: str | None,
) -> list[dict[str, Any]] | None:
    """Resolve ChatKit supported models from inline JSON or a JSON file."""
    if not models and not models_file:
        return None
    if models and models_file:
        raise CLIError(
            "Provide either --chatkit-models or --chatkit-models-file, not both."
        )

    if models:
        try:
            raw_payload = json.loads(models)
        except json.JSONDecodeError as exc:  # pragma: no cover - converted to CLIError
            raise CLIError(f"Invalid JSON payload: {exc}") from exc
    else:
        assert models_file is not None
        path_obj = _validate_local_path(models_file, description="chatkit models")
        raw_payload = json.loads(path_obj.read_text(encoding="utf-8"))

    if not isinstance(raw_payload, list):
        raise CLIError("ChatKit models payload must be a JSON array.")

    return [
        _normalize_chatkit_model_entry(entry, index=index)
        for index, entry in enumerate(raw_payload, start=1)
    ]


def _resolve_evaluation_payload(
    evaluation: str | None,
    evaluation_file: str | None,
) -> dict[str, Any]:
    """Resolve an evaluation payload from inline JSON or file."""
    if not evaluation and not evaluation_file:
        raise CLIError("Provide --evaluation or --evaluation-file for evaluation runs.")
    if evaluation and evaluation_file:
        raise CLIError("Provide either --evaluation or --evaluation-file, not both.")
    if evaluation:
        payload = _load_inputs_from_string(evaluation)
    else:
        assert evaluation_file is not None
        payload = _load_inputs_from_path(evaluation_file)
    return dict(payload)


def _cache_notice(state: CLIState, subject: str, stale: bool) -> None:
    """Display cache usage notice in the console."""
    if not state.human:
        return
    note = "[yellow]Using cached data[/yellow]"
    if stale:
        note += " (older than TTL)"
    state.console.print(f"{note} for {subject}.")


__all__ = [
    "_resolve_run_inputs",
    "_load_inputs_from_string",
    "_validate_local_path",
    "_load_inputs_from_path",
    "_resolve_runnable_config",
    "_resolve_chatkit_start_screen_prompts",
    "_resolve_chatkit_supported_models",
    "_resolve_evaluation_payload",
    "_cache_notice",
]
