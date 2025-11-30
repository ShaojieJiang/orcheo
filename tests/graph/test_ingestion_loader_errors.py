"""Tests for ingestion loader error handling."""

from __future__ import annotations
from orcheo.graph.ingestion import loader


def test_format_syntax_error_with_line_prefix() -> None:
    """Test _format_syntax_error_message with 'Line' prefix."""
    exc = SyntaxError("Line 39: AnnAssign statements are not allowed.")
    result = loader._format_syntax_error_message(exc)
    assert result == "Compilation error: Line 39: AnnAssign statements are not allowed."


def test_format_syntax_error_with_multiple_string_args() -> None:
    """Test _format_syntax_error_message with multiple string args."""
    exc = SyntaxError()
    exc.args = ("Error 1", "Error 2", "Error 3")
    result = loader._format_syntax_error_message(exc)
    assert result == "Compilation error: Error 1, Error 2, Error 3"


def test_format_syntax_error_with_mixed_args() -> None:
    """Test _format_syntax_error_message with mixed arg types."""
    exc = SyntaxError()
    exc.args = ("String error", 123, "Another string")
    result = loader._format_syntax_error_message(exc)
    assert result == "Compilation error: String error, Another string"


def test_format_syntax_error_without_string_args() -> None:
    """Test _format_syntax_error_message without string args."""
    exc = SyntaxError()
    exc.args = (123, 456)
    result = loader._format_syntax_error_message(exc)
    assert result.startswith("Compilation error:")


def test_format_syntax_error_without_args() -> None:
    """Test _format_syntax_error_message without args."""
    exc = SyntaxError()
    result = loader._format_syntax_error_message(exc)
    assert result.startswith("Compilation error:")


def test_returns_state_graph_handles_type_error() -> None:
    """Ensure _returns_state_graph returns False when inspect.signature fails."""
    assert loader._returns_state_graph(object()) is False


def test_returns_state_graph_handles_value_error() -> None:
    """Ensure _returns_state_graph handles ValueError from inspect.signature."""
    assert loader._returns_state_graph(type) is False


def test_returns_state_graph_requires_return_annotation() -> None:
    """Ensure callables without return annotations do not qualify."""

    def builder():
        return None

    assert loader._returns_state_graph(builder) is False


def test_is_state_graph_annotation_accepts_forward_refs() -> None:
    """String annotations referencing graphs should be accepted."""
    assert loader._is_state_graph_annotation("StateGraph") is True
    assert loader._is_state_graph_annotation("CompiledStateGraph") is True


def test_is_state_graph_annotation_accepts_generic_origin(monkeypatch) -> None:
    """Annotations whose origin is a graph class should be treated as graphs."""
    sentinel = object()
    original_get_origin = loader.get_origin

    def fake_get_origin(value):
        if value is sentinel:
            return loader.StateGraph
        return original_get_origin(value)

    monkeypatch.setattr(loader, "get_origin", fake_get_origin)
    assert loader._is_state_graph_annotation(sentinel) is True
