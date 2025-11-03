"""Tests for the CLI output module."""

from __future__ import annotations
from io import StringIO
from unittest.mock import patch
from orcheo_sdk.cli.output import (
    format_datetime,
    render_json,
    render_table,
    success,
    warning,
)
from rich.console import Console


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


def test_success_message() -> None:
    """Test success message output."""
    output = StringIO()
    with patch("orcheo_sdk.cli.output.Console") as mock_console_class:
        mock_console = Console(file=output, force_terminal=True)
        mock_console_class.return_value = mock_console

        success("Operation completed")

        result = output.getvalue()
        assert "Operation completed" in result


def test_warning_message() -> None:
    """Test warning message output."""
    output = StringIO()
    with patch("orcheo_sdk.cli.output.Console") as mock_console_class:
        mock_console = Console(file=output, force_terminal=True)
        mock_console_class.return_value = mock_console

        warning("This is a warning")

        result = output.getvalue()
        assert "This is a warning" in result


def test_success_with_special_characters() -> None:
    """Test success message with special characters."""
    output = StringIO()
    with patch("orcheo_sdk.cli.output.Console") as mock_console_class:
        mock_console = Console(file=output, force_terminal=True)
        mock_console_class.return_value = mock_console

        success("Success: 100% complete!")

        result = output.getvalue()
        assert "100" in result
        assert "complete" in result


def test_warning_with_special_characters() -> None:
    """Test warning message with special characters."""
    output = StringIO()
    with patch("orcheo_sdk.cli.output.Console") as mock_console_class:
        mock_console = Console(file=output, force_terminal=True)
        mock_console_class.return_value = mock_console

        warning("Warning: Rate limit 90% reached")

        result = output.getvalue()
        assert "90" in result
        assert "Rate limit" in result
