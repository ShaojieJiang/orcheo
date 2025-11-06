"""Node output rendering helper tests."""

from __future__ import annotations
from types import SimpleNamespace


def test_render_node_output_small_dict() -> None:
    """Test _render_node_output with small dict."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    data = {"status": "ok", "count": 42, "flag": True}
    _render_node_output(state, data)
    output_text = output.getvalue()
    assert "status" in output_text
    assert "ok" in output_text


def test_render_node_output_large_dict() -> None:
    """Test _render_node_output with large dict."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    data = {"a": 1, "b": 2, "c": 3, "d": 4}
    _render_node_output(state, data)
    # Should use JSON rendering for dicts with more than 3 keys
    output_text = output.getvalue()
    assert output_text  # Should have some output


def test_render_node_output_dict_complex_values() -> None:
    """Test _render_node_output with dict containing complex values."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    data = {"nested": {"value": 1}, "list": [1, 2, 3]}
    _render_node_output(state, data)
    output_text = output.getvalue()
    assert output_text  # Should have some output


def test_render_node_output_short_string() -> None:
    """Test _render_node_output with short string."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    data = "Hello world"
    _render_node_output(state, data)
    assert "Hello world" in output.getvalue()


def test_render_node_output_long_string() -> None:
    """Test _render_node_output with long string."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    data = "x" * 150
    _render_node_output(state, data)
    output_text = output.getvalue()
    assert output_text  # Should have some output


def test_render_node_output_other_type() -> None:
    """Test _render_node_output with other data types."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    data = [1, 2, 3, 4, 5]
    _render_node_output(state, data)
    output_text = output.getvalue()
    assert output_text  # Should have some output


def test_render_node_output_none() -> None:
    """Test _render_node_output with None."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    _render_node_output(state, None)
    # Should not output anything for None
    assert output.getvalue() == ""


def test_render_node_output_empty_dict() -> None:
    """Test _render_node_output with empty dict."""
    import io
    from orcheo_sdk.cli.workflow import _render_node_output
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    _render_node_output(state, {})
    # Empty dict should not output anything
    assert output.getvalue() == ""
