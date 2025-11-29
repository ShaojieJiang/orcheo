"""Tests for ingestion loader error handling."""

from __future__ import annotations
from orcheo.graph.ingestion.loader import _format_syntax_error_message


def test_format_syntax_error_with_line_prefix() -> None:
    """Test _format_syntax_error_message with 'Line' prefix."""
    exc = SyntaxError("Line 39: AnnAssign statements are not allowed.")
    result = _format_syntax_error_message(exc)
    assert result == "Compilation error: Line 39: AnnAssign statements are not allowed."


def test_format_syntax_error_with_multiple_string_args() -> None:
    """Test _format_syntax_error_message with multiple string args."""
    exc = SyntaxError()
    exc.args = ("Error 1", "Error 2", "Error 3")
    result = _format_syntax_error_message(exc)
    assert result == "Compilation error: Error 1, Error 2, Error 3"


def test_format_syntax_error_with_mixed_args() -> None:
    """Test _format_syntax_error_message with mixed arg types."""
    exc = SyntaxError()
    exc.args = ("String error", 123, "Another string")
    result = _format_syntax_error_message(exc)
    assert result == "Compilation error: String error, Another string"


def test_format_syntax_error_without_string_args() -> None:
    """Test _format_syntax_error_message without string args."""
    exc = SyntaxError()
    exc.args = (123, 456)
    result = _format_syntax_error_message(exc)
    assert result.startswith("Compilation error:")


def test_format_syntax_error_without_args() -> None:
    """Test _format_syntax_error_message without args."""
    exc = SyntaxError()
    result = _format_syntax_error_message(exc)
    assert result.startswith("Compilation error:")
