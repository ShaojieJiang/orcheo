"""Workflow upload helpers."""

from __future__ import annotations
from collections.abc import Callable
from pathlib import Path
from typing import Any
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.http import ApiClient


def _load_workflow_config_from_path(
    path_obj: Path,
    *,
    load_python: Callable[[Path], dict[str, Any]],
    load_json: Callable[[Path], dict[str, Any]],
) -> dict[str, Any]:
    """Load a workflow configuration from disk supporting python/json."""
    file_extension = path_obj.suffix.lower()
    if file_extension not in {".py", ".json"}:
        raise CLIError(
            f"Unsupported file type '{file_extension}'. Use .py or .json files."
        )

    try:
        if file_extension == ".py":
            return load_python(path_obj)
        return load_json(path_obj)
    except CLIError:
        raise
    except Exception as exc:  # pragma: no cover - defensive error context
        raise CLIError(
            f"Failed to load workflow definition from '{path_obj}'."
        ) from exc


def _upload_langgraph_workflow(
    state: Any,
    workflow_config: dict[str, Any],
    workflow_id: str | None,
    path_obj: Path,
    requested_name: str | None,
    *,
    uploader: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    """Upload a LangGraph workflow script via CLI helper."""
    try:
        return uploader(
            state,
            workflow_config,
            workflow_id,
            path_obj,
            requested_name,
        )
    except CLIError:
        raise
    except Exception as exc:  # pragma: no cover - defensive error context
        raise CLIError("Failed to upload LangGraph workflow script via API.") from exc


def _submit_workflow_configuration(
    client: ApiClient,
    workflow_config: dict[str, Any],
    workflow_id: str | None,
) -> dict[str, Any]:
    """Submit workflow configuration payload to Orcheo."""
    url = f"/api/workflows/{workflow_id}" if workflow_id else "/api/workflows"
    try:
        return client.post(url, json_body=workflow_config)
    except Exception as exc:  # pragma: no cover - http errors handled upstream
        raise CLIError("Failed to upload workflow configuration to Orcheo.") from exc


def upload_workflow_data(
    client: ApiClient,
    file_path: str | Path,
    workflow_id: str | None = None,
    workflow_name: str | None = None,
    entrypoint: str | None = None,
    console: Any | None = None,
) -> dict[str, Any]:
    """Upload workflow definition from a local file."""
    from orcheo_sdk.cli.workflow import (
        _load_workflow_from_json,
        _load_workflow_from_python,
        _normalize_workflow_name,
        _upload_langgraph_script,
        _validate_local_path,
    )

    class MinimalState:
        def __init__(self, client_obj: Any, console_obj: Any | None) -> None:
            self.client = client_obj
            self.console = console_obj or _FakeConsole()

    class _FakeConsole:
        def print(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - noop
            pass

    state = MinimalState(client, console)
    requested_name = _normalize_workflow_name(workflow_name)
    path_obj = _validate_local_path(file_path, description="workflow")

    workflow_config = _load_workflow_config_from_path(
        path_obj,
        load_python=_load_workflow_from_python,
        load_json=_load_workflow_from_json,
    )

    if workflow_config.get("_type") == "langgraph_script":
        if entrypoint:
            workflow_config["entrypoint"] = entrypoint
        result = _upload_langgraph_workflow(
            state,  # type: ignore[arg-type]
            workflow_config,
            workflow_id,
            path_obj,
            requested_name,
            uploader=_upload_langgraph_script,
        )
    else:
        if requested_name:
            workflow_config["name"] = requested_name
        result = _submit_workflow_configuration(
            client,
            workflow_config,
            workflow_id,
        )

    return result
