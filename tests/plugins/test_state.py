"""Tests for the plugin state persistence module."""

from __future__ import annotations
from pathlib import Path
import pytest
from orcheo.plugins.models import DesiredPluginRecord, LockedPluginRecord
from orcheo.plugins.state import (
    _atomic_write,
    _dump_records,
    _format_toml_value,
    load_desired_state,
    load_lock_state,
    save_desired_state,
    save_lock_state,
)


# ---------------------------------------------------------------------------
# _format_toml_value
# ---------------------------------------------------------------------------


def test_format_toml_bool_true() -> None:
    assert _format_toml_value(True) == "true"


def test_format_toml_bool_false() -> None:
    assert _format_toml_value(False) == "false"


def test_format_toml_int() -> None:
    assert _format_toml_value(42) == "42"


def test_format_toml_str_plain() -> None:
    assert _format_toml_value("hello") == '"hello"'


def test_format_toml_str_escapes() -> None:
    assert _format_toml_value('a"b\\c') == '"a\\"b\\\\c"'


def test_format_toml_list() -> None:
    assert _format_toml_value(["nodes", "edges"]) == '["nodes", "edges"]'


def test_format_toml_unsupported_type_raises() -> None:
    """TypeError is raised for unsupported types (lines 24-25)."""
    with pytest.raises(TypeError, match="Unsupported TOML value"):
        _format_toml_value({"key": "value"})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _atomic_write
# ---------------------------------------------------------------------------


def test_atomic_write_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "subdir" / "file.toml"
    _atomic_write(target, "hello = true\n")
    assert target.read_text(encoding="utf-8") == "hello = true\n"
    assert not target.with_suffix(".toml.tmp").exists()


def test_atomic_write_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "file.toml"
    target.write_text("old", encoding="utf-8")
    _atomic_write(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


# ---------------------------------------------------------------------------
# _dump_records
# ---------------------------------------------------------------------------


def test_dump_records_empty() -> None:
    assert _dump_records([]) == ""


def test_dump_records_one_record() -> None:
    records = [{"name": "my-plugin", "source": "path/to/pkg", "enabled": True}]
    result = _dump_records(records)
    assert "[[plugin]]" in result
    assert 'name = "my-plugin"' in result
    assert "enabled = true" in result


def test_dump_records_skips_none_values() -> None:
    records = [{"name": "plugin", "source": "src", "status": None}]
    result = _dump_records(records)
    assert "status" not in result


# ---------------------------------------------------------------------------
# load_desired_state / save_desired_state
# ---------------------------------------------------------------------------


def test_load_desired_state_missing_file(tmp_path: Path) -> None:
    result = load_desired_state(tmp_path / "missing.toml")
    assert result == []


def test_save_and_load_desired_state_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "plugins.toml"
    records = [
        DesiredPluginRecord(
            name="my-plugin",
            source="./my_plugin",
            enabled=True,
            install_source="cli",
        ),
        DesiredPluginRecord(
            name="other-plugin",
            source="other-pkg",
            enabled=False,
            status="error",
            last_error="something went wrong",
        ),
    ]
    save_desired_state(path, records)
    loaded = load_desired_state(path)
    assert len(loaded) == 2
    by_name = {r.name: r for r in loaded}
    assert by_name["my-plugin"].enabled is True
    assert by_name["other-plugin"].enabled is False
    assert by_name["other-plugin"].last_error == "something went wrong"


def test_load_desired_state_skips_invalid_entries(tmp_path: Path) -> None:
    """Entries without name or source are silently skipped."""
    path = tmp_path / "plugins.toml"
    path.write_text(
        '[[plugin]]\nname = ""\nsource = "src"\n\n'
        '[[plugin]]\nname = "ok"\nsource = "ok-src"\n',
        encoding="utf-8",
    )
    loaded = load_desired_state(path)
    assert len(loaded) == 1
    assert loaded[0].name == "ok"


# ---------------------------------------------------------------------------
# load_lock_state / save_lock_state
# ---------------------------------------------------------------------------


def test_load_lock_state_missing_file(tmp_path: Path) -> None:
    result = load_lock_state(tmp_path / "missing.toml")
    assert result == []


def test_save_and_load_lock_state_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "plugin-lock.toml"
    records = [
        LockedPluginRecord(
            name="my-plugin",
            version="1.0.0",
            plugin_api_version=1,
            orcheo_version=">=0.1.0",
            location="/some/path",
            wheel_sha256="abc",
            manifest_sha256="def",
            exports=["nodes"],
            description="A plugin",
            author="Author",
            entry_points=["main=my_plugin:register"],
        )
    ]
    save_lock_state(path, records)
    loaded = load_lock_state(path)
    assert len(loaded) == 1
    assert loaded[0].name == "my-plugin"
    assert loaded[0].exports == ["nodes"]


def test_load_lock_state_skips_non_dict_items(tmp_path: Path) -> None:
    """Non-dict items in plugin list are skipped (line 86)."""
    from unittest.mock import patch

    path = tmp_path / "plugin-lock.toml"
    path.write_text("", encoding="utf-8")
    with patch(
        "orcheo.plugins.state.tomllib.loads",
        return_value={"plugin": ["not-a-dict", {"name": "ok", "version": "1.0.0"}]},
    ):
        loaded = load_lock_state(path)
    assert len(loaded) == 1
    assert loaded[0].name == "ok"


def test_load_lock_state_skips_missing_version(tmp_path: Path) -> None:
    """Items without version are skipped (line 88)."""
    path = tmp_path / "plugin-lock.toml"
    path.write_text(
        '[[plugin]]\nname = "only-name"\n\n'
        '[[plugin]]\nname = "has-both"\nversion = "2.0.0"\n',
        encoding="utf-8",
    )
    loaded = load_lock_state(path)
    assert len(loaded) == 1
    assert loaded[0].name == "has-both"
