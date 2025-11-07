"""Tests for filesystem and serialization helpers in the workflow CLI."""

from __future__ import annotations
from pathlib import Path
from typing import Any
import pytest
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.workflow import (
    _load_inputs_from_path,
    _mermaid_from_graph,
    _strip_main_block,
    _validate_local_path,
)


def test_load_inputs_from_path_blocks_traversal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    outside_inputs = tmp_path.parent / "inputs.json"
    outside_inputs.write_text("{}", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    with pytest.raises(CLIError) as excinfo:
        _load_inputs_from_path("../inputs.json")

    assert "escapes the current working directory" in str(excinfo.value)


def test_load_inputs_from_path_allows_relative_inside_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    payload_file = tmp_path / "inputs.json"
    payload_file.write_text('{"value": 1}', encoding="utf-8")

    payload = _load_inputs_from_path("inputs.json")

    assert payload == {"value": 1}


def test_validate_local_path_requires_existing_parent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(CLIError) as excinfo:
        _validate_local_path(
            "missing-dir/output.json",
            description="output",
            must_exist=False,
            require_file=True,
        )

    assert "does not exist" in str(excinfo.value)


def test_validate_local_path_rejects_non_directory_parent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    parent_file = tmp_path / "parent.txt"
    parent_file.write_text("content", encoding="utf-8")

    with pytest.raises(CLIError) as excinfo:
        _validate_local_path(
            "parent.txt/output.json",
            description="output",
            must_exist=False,
            require_file=True,
        )

    assert "not a directory" in str(excinfo.value)


def test_validate_local_path_rejects_existing_directory_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    existing_dir = tmp_path / "existing"
    existing_dir.mkdir()

    with pytest.raises(CLIError) as excinfo:
        _validate_local_path(
            "existing",
            description="output",
            must_exist=False,
            require_file=True,
        )

    assert "not a file" in str(excinfo.value)


def test_strip_main_block_stops_on_double_quote() -> None:
    script = "print('hello')\nif __name__ == \"__main__\":\n    run()\nmore()"
    result = _strip_main_block(script)
    assert result == "print('hello')"


def test_strip_main_block_stops_on_single_quote() -> None:
    script = "print('hello')\nif __name__ == '__main__':\n    run()"
    result = _strip_main_block(script)
    assert result == "print('hello')"


def test_mermaid_from_graph_handles_non_mapping_graph() -> None:
    class FakeGraph:
        def __init__(self) -> None:
            self._data = {"nodes": [], "edges": []}

        def get(self, key: str, default: Any = None) -> Any:
            return self._data.get(key, default)

    mermaid = _mermaid_from_graph(FakeGraph())
    assert "__start__" in mermaid
    assert "__end__" in mermaid
