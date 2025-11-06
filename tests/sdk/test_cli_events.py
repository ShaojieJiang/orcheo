"""Status update and node event rendering tests."""

from __future__ import annotations
from types import SimpleNamespace


def test_handle_status_update_error() -> None:
    """Test _handle_status_update with error status."""
    import io
    from orcheo_sdk.cli.workflow import _handle_status_update
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"status": "error", "error": "Something went wrong"}
    result = _handle_status_update(state, update)
    assert result == "error"
    assert "Something went wrong" in output.getvalue()


def test_handle_status_update_error_no_detail() -> None:
    """Test _handle_status_update with error status but no error detail."""
    import io
    from orcheo_sdk.cli.workflow import _handle_status_update
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"status": "error"}
    result = _handle_status_update(state, update)
    assert result == "error"
    assert "Unknown error" in output.getvalue()


def test_handle_status_update_cancelled() -> None:
    """Test _handle_status_update with cancelled status."""
    import io
    from orcheo_sdk.cli.workflow import _handle_status_update
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"status": "cancelled", "reason": "User stopped it"}
    result = _handle_status_update(state, update)
    assert result == "cancelled"
    assert "User stopped it" in output.getvalue()


def test_handle_status_update_cancelled_no_reason() -> None:
    """Test _handle_status_update with cancelled status but no reason."""
    import io
    from orcheo_sdk.cli.workflow import _handle_status_update
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"status": "cancelled"}
    result = _handle_status_update(state, update)
    assert result == "cancelled"
    assert "No reason provided" in output.getvalue()


def test_handle_status_update_completed() -> None:
    """Test _handle_status_update with completed status."""
    import io
    from orcheo_sdk.cli.workflow import _handle_status_update
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"status": "completed"}
    result = _handle_status_update(state, update)
    assert result == "completed"
    assert "completed successfully" in output.getvalue()


def test_handle_status_update_other_status() -> None:
    """Test _handle_status_update with other status."""
    import io
    from orcheo_sdk.cli.workflow import _handle_status_update
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"status": "running"}
    result = _handle_status_update(state, update)
    assert result is None
    assert "running" in output.getvalue()


def test_handle_node_event_on_chain_start() -> None:
    """Test _handle_node_event with on_chain_start event."""
    import io
    from orcheo_sdk.cli.workflow import _handle_node_event
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"node": "test_node", "event": "on_chain_start"}
    _handle_node_event(state, update)
    assert "test_node" in output.getvalue()
    assert "starting" in output.getvalue()


def test_handle_node_event_on_chain_end() -> None:
    """Test _handle_node_event with on_chain_end event."""
    import io
    from orcheo_sdk.cli.workflow import _handle_node_event
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {
        "node": "test_node",
        "event": "on_chain_end",
        "payload": {"result": "success"},
    }
    _handle_node_event(state, update)
    assert "test_node" in output.getvalue()


def test_handle_node_event_on_chain_error() -> None:
    """Test _handle_node_event with on_chain_error event."""
    import io
    from orcheo_sdk.cli.workflow import _handle_node_event
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {
        "node": "test_node",
        "event": "on_chain_error",
        "payload": {"error": "Failed to process"},
    }
    _handle_node_event(state, update)
    assert "test_node" in output.getvalue()
    assert "Failed to process" in output.getvalue()


def test_handle_node_event_on_chain_error_no_payload() -> None:
    """Test _handle_node_event with on_chain_error event but no payload."""
    import io
    from orcheo_sdk.cli.workflow import _handle_node_event
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"node": "test_node", "event": "on_chain_error"}
    _handle_node_event(state, update)
    assert "test_node" in output.getvalue()
    assert "Unknown" in output.getvalue()


def test_handle_node_event_other_event() -> None:
    """Test _handle_node_event with other event types."""
    import io
    from orcheo_sdk.cli.workflow import _handle_node_event
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"node": "test_node", "event": "on_chain_stream", "data": "some data"}
    _handle_node_event(state, update)
    assert "test_node" in output.getvalue()
    assert "on_chain_stream" in output.getvalue()


def test_handle_node_event_no_node() -> None:
    """Test _handle_node_event with no node field."""
    import io
    from orcheo_sdk.cli.workflow import _handle_node_event
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"event": "on_chain_start"}
    _handle_node_event(state, update)
    # Should not print anything
    assert output.getvalue() == ""


def test_handle_node_event_no_event() -> None:
    """Test _handle_node_event with no event field."""
    import io
    from orcheo_sdk.cli.workflow import _handle_node_event
    from rich.console import Console

    output = io.StringIO()
    console = Console(file=output, force_terminal=False, no_color=True, markup=False)
    state = SimpleNamespace(console=console)

    update = {"node": "test_node"}
    _handle_node_event(state, update)
    # Should not print anything
    assert output.getvalue() == ""
