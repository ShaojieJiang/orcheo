"""Targeted tests for the workflow CLI input helpers."""

from __future__ import annotations
import io
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from rich.console import Console
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.workflow.inputs import (
    _cache_notice,
    _load_inputs_from_string,
    _normalize_chatkit_model_entry,
    _normalize_chatkit_prompt_entry,
    _optional_chatkit_model_bool,
    _optional_chatkit_model_string,
    _required_chatkit_model_string,
    _resolve_chatkit_start_screen_prompts,
    _resolve_chatkit_supported_models,
    _resolve_evaluation_payload,
    _resolve_run_inputs,
    _resolve_runnable_config,
)


def _capture_console_output() -> tuple[Console, io.StringIO]:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False)
    return console, buffer


def test_resolve_run_inputs_requires_single_source(tmp_path: Path) -> None:
    payload_file = tmp_path / "payload.json"
    payload_file.write_text("{}", encoding="utf-8")

    with pytest.raises(CLIError, match="either --inputs or --inputs-file"):
        _resolve_run_inputs("{}", str(payload_file))


def test_resolve_run_inputs_prefers_inline_string() -> None:
    data = {"foo": "bar"}

    payload = _resolve_run_inputs(json.dumps(data), None)

    assert payload == data


def test_resolve_run_inputs_reads_file(tmp_path: Path) -> None:
    payload = {"value": 1}
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(json.dumps(payload), encoding="utf-8")

    assert _resolve_run_inputs(None, str(payload_file)) == payload


def test_load_inputs_from_string_rejects_invalid_json() -> None:
    with pytest.raises(CLIError, match="Invalid JSON payload"):
        _load_inputs_from_string("not-json")


def test_load_inputs_from_string_rejects_non_object() -> None:
    with pytest.raises(CLIError, match="must be a JSON object"):
        _load_inputs_from_string("[1,2,3]")


def test_normalize_prompt_entry_trims_simple_string() -> None:
    payload = _normalize_chatkit_prompt_entry("  hello  ", index=1)

    assert payload == {"label": "hello", "prompt": "hello"}


def test_normalize_prompt_entry_handles_explicit_fields() -> None:
    entry = {
        "label": " Label ",
        "prompt": "Prompt ",
        "icon": " icon ",
    }

    payload = _normalize_chatkit_prompt_entry(entry, index=1)

    assert payload == {
        "label": "Label",
        "prompt": "Prompt",
        "icon": "icon",
    }


def test_normalize_prompt_entry_rejects_empty_string() -> None:
    with pytest.raises(CLIError, match="must not be an empty string"):
        _normalize_chatkit_prompt_entry("  \t  ", index=2)


def test_normalize_prompt_entry_requires_object_or_string() -> None:
    with pytest.raises(CLIError, match="must be a string or JSON object"):
        _normalize_chatkit_prompt_entry(123, index=3)


def test_normalize_prompt_entry_rejects_extra_keys() -> None:
    entry = {"label": "Label", "prompt": "Prompt", "extra": 1}
    with pytest.raises(CLIError, match="unsupported keys"):
        _normalize_chatkit_prompt_entry(entry, index=4)


def test_normalize_prompt_entry_requires_label_prompt_and_icon() -> None:
    with pytest.raises(CLIError, match="requires a non-empty label"):
        _normalize_chatkit_prompt_entry({"label": "", "prompt": "Hi"}, index=5)
    with pytest.raises(CLIError, match="requires a non-empty prompt"):
        _normalize_chatkit_prompt_entry({"label": "Label", "prompt": ""}, index=6)
    with pytest.raises(CLIError, match="icon must be a non-empty string"):
        _normalize_chatkit_prompt_entry(
            {"label": "Label", "prompt": "Prompt", "icon": 1},
            index=7,
        )


def test_resolve_chatkit_start_screen_prompts_prefers_single_source(
    tmp_path: Path,
) -> None:
    prompts_file = tmp_path / "prompts.json"
    prompts_file.write_text("[]", encoding="utf-8")

    with pytest.raises(
        CLIError, match="either --chatkit-prompts or --chatkit-prompts-file"
    ):
        _resolve_chatkit_start_screen_prompts("[]", str(prompts_file))


def test_resolve_chatkit_start_screen_prompts_requires_list() -> None:
    with pytest.raises(CLIError, match="must be a JSON array"):
        _resolve_chatkit_start_screen_prompts("{}", None)


def test_resolve_chatkit_start_screen_prompts_from_string() -> None:
    prompts = json.dumps(
        [
            {"label": "One", "prompt": "One"},
            "Two",
        ]
    )

    payload = _resolve_chatkit_start_screen_prompts(prompts, None)

    assert payload[0]["label"] == "One"
    assert payload[1]["label"] == "Two"


def test_resolve_chatkit_start_screen_prompts_from_file(tmp_path: Path) -> None:
    prompts = [{"label": "Entry", "prompt": "Entry"}]
    prompts_file = tmp_path / "prompts.json"
    prompts_file.write_text(json.dumps(prompts), encoding="utf-8")

    payload = _resolve_chatkit_start_screen_prompts(None, str(prompts_file))

    assert payload[0]["label"] == "Entry"


def test_normalize_model_entry_allows_strings() -> None:
    payload = _normalize_chatkit_model_entry("  foo  ", index=1)

    assert payload == {"id": "foo", "label": "foo"}


def test_normalize_model_entry_rejects_invalid_inputs() -> None:
    with pytest.raises(CLIError, match="must not be an empty string"):
        _normalize_chatkit_model_entry("  ", index=2)
    with pytest.raises(CLIError, match="must be a string or JSON object"):
        _normalize_chatkit_model_entry(123, index=3)


def test_normalize_model_entry_rejects_extra_keys() -> None:
    with pytest.raises(CLIError, match="unsupported keys"):
        _normalize_chatkit_model_entry({"id": "one", "extra": True}, index=4)


def test_normalize_model_entry_includes_optional_fields() -> None:
    payload = _normalize_chatkit_model_entry(
        {
            "id": "one",
            "label": "Label",
            "description": "Desc",
            "default": True,
            "disabled": False,
        },
        index=5,
    )

    assert payload["description"] == "Desc"
    assert payload["default"] is True
    assert payload["disabled"] is False


def test_optional_model_string_rejects_invalid_types() -> None:
    with pytest.raises(CLIError, match="must be a non-empty string"):
        _optional_chatkit_model_string(1, index=1, key="label")


def test_optional_model_bool_rejects_invalid_types() -> None:
    with pytest.raises(CLIError, match="must be a boolean"):
        _optional_chatkit_model_bool("yes", index=1, key="default")


def test_resolve_chatkit_supported_models_requires_single_source(
    tmp_path: Path,
) -> None:
    models_file = tmp_path / "models.json"
    models_file.write_text("[]", encoding="utf-8")

    with pytest.raises(
        CLIError, match="either --chatkit-models or --chatkit-models-file"
    ):
        _resolve_chatkit_supported_models("[]", str(models_file))


def test_resolve_chatkit_supported_models_requires_list() -> None:
    with pytest.raises(CLIError, match="must be a JSON array"):
        _resolve_chatkit_supported_models("{}", None)


def test_resolve_chatkit_supported_models_from_file(tmp_path: Path) -> None:
    dataset = [{"id": "foo"}]
    models_file = tmp_path / "models.json"
    models_file.write_text(json.dumps(dataset), encoding="utf-8")

    payload = _resolve_chatkit_supported_models(None, str(models_file))

    assert payload[0]["id"] == "foo"


def test_resolve_evaluation_payload_requires_source(tmp_path: Path) -> None:
    payload_file = tmp_path / "payload.json"
    payload_file.write_text("{}", encoding="utf-8")

    with pytest.raises(CLIError, match="Provide --evaluation or --evaluation-file"):
        _resolve_evaluation_payload(None, None)

    with pytest.raises(CLIError, match="either --evaluation or --evaluation-file"):
        _resolve_evaluation_payload("{}", str(payload_file))


def test_resolve_evaluation_payload_prefers_inline_string() -> None:
    payload = _resolve_evaluation_payload('{"key": "value"}', None)

    assert payload == {"key": "value"}


def test_resolve_evaluation_payload_reads_file(tmp_path: Path) -> None:
    payload_file = tmp_path / "payload.json"
    payload_file.write_text('{"nested": 1}', encoding="utf-8")

    payload = _resolve_evaluation_payload(None, str(payload_file))

    assert payload == {"nested": 1}


def test_resolve_runnable_config_rejects_both_sources(tmp_path: Path) -> None:
    """Providing both config and config_file raises CLIError (line 98)."""
    config_file = tmp_path / "config.json"
    config_file.write_text("{}", encoding="utf-8")

    with pytest.raises(CLIError, match="either --config or --config-file"):
        _resolve_runnable_config('{"key": 1}', str(config_file))


def test_resolve_runnable_config_rejects_non_mapping_json() -> None:
    """Inline config that is not a JSON object raises CLIError (lines 105-106)."""
    with pytest.raises(CLIError, match="must be a JSON object"):
        _resolve_runnable_config("[1, 2, 3]", None)


def test_required_chatkit_model_string_raises_when_value_is_none() -> None:
    """None value for a required model field raises CLIError (line 259)."""
    with pytest.raises(CLIError, match="requires a non-empty id"):
        _required_chatkit_model_string(None, index=1, key="id")


def test_cache_notice_handles_human_and_stale_flags() -> None:
    console, buffer = _capture_console_output()
    state = SimpleNamespace(human=False, console=console)

    _cache_notice(state, "workflow", stale=False)
    assert buffer.getvalue() == ""

    console, buffer = _capture_console_output()
    state = SimpleNamespace(human=True, console=console)
    _cache_notice(state, "workflow", stale=False)
    assert "Using cached data" in buffer.getvalue()
    assert "older than TTL" not in buffer.getvalue()

    console, buffer = _capture_console_output()
    state = SimpleNamespace(human=True, console=console)
    _cache_notice(state, "workflow", stale=True)
    assert "older than TTL" in buffer.getvalue()
