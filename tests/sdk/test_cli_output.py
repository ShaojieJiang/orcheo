"""Tests for the CLI output module."""

from __future__ import annotations
from io import StringIO
import pytest
from rich.console import Console
from orcheo_sdk.cli.output import (
    format_datetime,
    render_json,
    render_table,
    success,
    warning,
)


def test_render_table_basic() -> None:
    """Test rendering a basic table."""
    output = StringIO()
    console = Console(file=output, force_terminal=True, width=80)

    render_table(
        console,
        title="Test Table",
        columns=["Column 1", "Column 2"],
        rows=[["Value 1", "Value 2"], ["Value 3", "Value 4"]],
    )

    result = output.getvalue()
    assert "Test Table" in result
    assert "Column 1" in result
    assert "Column 2" in result
    assert "Value 1" in result
    assert "Value 2" in result


def test_render_table_with_numbers() -> None:
    """Test rendering a table with numeric values."""
    output = StringIO()
    console = Console(file=output, force_terminal=True, width=80)

    render_table(
        console,
        title="Numbers",
        columns=["ID", "Count"],
        rows=[[1, 100], [2, 200]],
    )

    result = output.getvalue()
    assert "1" in result
    assert "100" in result


def test_render_json_with_title() -> None:
    """Test rendering JSON with a title."""
    output = StringIO()
    console = Console(file=output, force_terminal=True, width=80)

    payload = {"key": "value", "nested": {"inner": "data"}}
    render_json(console, payload, title="Test JSON")

    result = output.getvalue()
    assert "Test JSON" in result
    assert "key" in result
    assert "value" in result


def test_render_json_without_title() -> None:
    """Test rendering JSON without a title."""
    output = StringIO()
    console = Console(file=output, force_terminal=True, width=80)

    payload = {"simple": "object"}
    render_json(console, payload)

    result = output.getvalue()
    assert "simple" in result
    assert "object" in result


def test_format_datetime_valid_iso_string() -> None:
    """Test formatting a valid ISO datetime string."""
    iso_string = "2024-11-03T10:30:00Z"
    result = format_datetime(iso_string)
    assert "2024-11-03" in result
    assert "10:30:00 UTC" in result


def test_format_datetime_with_timezone() -> None:
    """Test formatting a datetime string with timezone."""
    iso_string = "2024-11-03T10:30:00+00:00"
    result = format_datetime(iso_string)
    assert "2024-11-03" in result
    assert "UTC" in result


def test_format_datetime_invalid_string() -> None:
    """Test formatting an invalid datetime string returns original."""
    invalid_string = "not-a-date"
    result = format_datetime(invalid_string)
    assert result == invalid_string


def test_format_datetime_empty_string() -> None:
    """Test formatting an empty string returns original."""
    result = format_datetime("")
    assert result == ""


def test_format_datetime_none_attribute() -> None:
    """Test formatting None-like value (AttributeError path)."""
    # This tests the AttributeError exception path
    result = format_datetime("2024-11-03")  # Valid but without Z or timezone
    # Should still work for simple ISO format
    assert "2024-11-03" in result


def test_success_message(capsys: pytest.CaptureFixture[str]) -> None:
    """Test success message output."""
    success("Operation completed")

    result = capsys.readouterr().out
    assert "Operation completed" in result


def test_warning_message(capsys: pytest.CaptureFixture[str]) -> None:
    """Test warning message output."""
    warning("This is a warning")

    result = capsys.readouterr().out
    assert "This is a warning" in result


def test_success_with_special_characters(capsys: pytest.CaptureFixture[str]) -> None:
    """Test success message with special characters."""
    success("Success: 100% complete!")

    result = capsys.readouterr().out
    assert "100" in result
    assert "complete" in result


def test_warning_with_special_characters(capsys: pytest.CaptureFixture[str]) -> None:
    """Test warning message with special characters."""
    warning("Warning: Rate limit 90% reached")

    result = capsys.readouterr().out
    assert "90" in result
    assert "Rate limit" in result
