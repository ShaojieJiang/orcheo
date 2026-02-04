"""Tests for workflow CLI input resolution helpers."""

from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock, call
import pytest
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.cli.workflow.inputs import (
    _cache_notice,
    _load_inputs_from_path,
    _load_inputs_from_string,
    _resolve_evaluation_payload,
    _resolve_run_inputs,
    _resolve_runnable_config,
    _validate_local_path,
)


def test_resolve_run_inputs_from_string() -> None:
    payload = '{"key": "value"}'
    resolved = _resolve_run_inputs(payload, None)
    assert resolved == {"key": "value"}


def test_resolve_run_inputs_from_file(tmp_path: Path) -> None:
    inputs_file = tmp_path / "inputs.json"
    inputs_file.write_text('{"flag": true}', encoding="utf-8")

    resolved = _resolve_run_inputs(None, str(inputs_file))
    assert resolved == {"flag": True}


def test_resolve_run_inputs_conflict() -> None:
    with pytest.raises(CLIError, match="either --inputs or --inputs-file"):
        _resolve_run_inputs("{}", "/tmp/inputs.json")


def test_resolve_runnable_config_from_string() -> None:
    config = '{"mode": "fast"}'
    resolved = _resolve_runnable_config(config, None)
    assert resolved == {"mode": "fast"}


def test_resolve_runnable_config_from_file(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text('{"retry": 3}', encoding="utf-8")

    resolved = _resolve_runnable_config(None, str(config_file))
    assert resolved == {"retry": 3}


def test_resolve_runnable_config_conflict(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text('{"retry": 1}', encoding="utf-8")

    with pytest.raises(CLIError, match="either --config or --config-file"):
        _resolve_runnable_config("{}", str(config_file))


def test_resolve_runnable_config_invalid_payload() -> None:
    with pytest.raises(CLIError, match="Runnable config payload must be a JSON object"):
        _resolve_runnable_config("[]", None)


def test_resolve_runnable_config_returns_none_when_missing() -> None:
    assert _resolve_runnable_config(None, None) is None


def test_resolve_evaluation_payload_requires_value() -> None:
    with pytest.raises(CLIError, match="Provide --evaluation or --evaluation-file"):
        _resolve_evaluation_payload(None, None)


def test_resolve_evaluation_payload_conflict(tmp_path: Path) -> None:
    eval_file = tmp_path / "evaluation.json"
    eval_file.write_text('{"dataset": {"cases": [{"inputs": {}}]}}', encoding="utf-8")

    with pytest.raises(CLIError, match="either --evaluation or --evaluation-file"):
        _resolve_evaluation_payload("{}", str(eval_file))


def test_resolve_evaluation_payload_from_file(tmp_path: Path) -> None:
    eval_file = tmp_path / "evaluation.json"
    eval_file.write_text('{"dataset": {"cases": [{"inputs": {}}]}}', encoding="utf-8")

    resolved = _resolve_evaluation_payload(None, str(eval_file))
    assert resolved["dataset"]["cases"][0]["inputs"] == {}


def test_resolve_evaluation_payload_from_string() -> None:
    payload = '{"dataset": {"cases": [{"inputs": {"value": 1}}]}}'
    resolved = _resolve_evaluation_payload(payload, None)
    assert resolved["dataset"]["cases"][0]["inputs"]["value"] == 1


def test_load_inputs_from_string_requires_mapping() -> None:
    with pytest.raises(CLIError, match="Inputs payload must be a JSON object"):
        _load_inputs_from_string("[]")


def test_load_inputs_from_path_requires_mapping(tmp_path: Path) -> None:
    inputs_file = tmp_path / "inputs.json"
    inputs_file.write_text("[]", encoding="utf-8")

    with pytest.raises(CLIError, match="Inputs payload must be a JSON object"):
        _load_inputs_from_path(str(inputs_file))


def test_validate_local_path_rejects_relative_outside() -> None:
    with pytest.raises(CLIError, match="escapes the current working directory"):
        _validate_local_path("..", description="inputs")


def test_validate_local_path_requires_existing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"

    with pytest.raises(CLIError, match="does not exist"):
        _validate_local_path(str(missing), description="inputs")


def test_validate_local_path_requires_file(tmp_path: Path) -> None:
    directory = tmp_path / "folder"
    directory.mkdir()

    with pytest.raises(CLIError, match="is not a file"):
        _validate_local_path(str(directory), description="inputs")


def test_validate_local_path_disallows_directory_when_not_required(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "folder"
    directory.mkdir()

    with pytest.raises(CLIError, match="is not a file"):
        _validate_local_path(
            str(directory), description="inputs", must_exist=False, require_file=True
        )


def test_validate_local_path_requires_parent_directory(tmp_path: Path) -> None:
    target_path = tmp_path / "missing" / "inputs.json"

    with pytest.raises(CLIError, match="does not exist"):
        _validate_local_path(
            str(target_path),
            description="config",
            must_exist=False,
        )


def test_validate_local_path_parent_must_be_directory(tmp_path: Path) -> None:
    parent_file = tmp_path / "parent-file"
    parent_file.write_text("", encoding="utf-8")

    child_path = parent_file / "child.json"

    with pytest.raises(CLIError, match="Parent of config path"):
        _validate_local_path(
            str(child_path),
            description="config",
            must_exist=False,
        )


def test_cache_notice_reports_staleness_flags() -> None:
    console = MagicMock()
    state = CLIState(
        settings=MagicMock(),
        client=MagicMock(),
        cache=MagicMock(),
        console=console,
        human=True,
    )

    _cache_notice(state, "workflow run", stale=False)
    _cache_notice(state, "evaluation", stale=True)
    console.print.assert_has_calls(
        [
            call("[yellow]Using cached data[/yellow] for workflow run."),
            call("[yellow]Using cached data[/yellow] (older than TTL) for evaluation."),
        ]
    )
