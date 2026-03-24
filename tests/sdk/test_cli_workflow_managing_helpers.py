"""Tests for helper utilities in workflow managing commands."""

from __future__ import annotations
import io
from rich.console import Console
from orcheo_sdk.cli.workflow.commands.managing import _print_downloaded_config_notice


def _console_buffer() -> tuple[Console, io.StringIO]:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False)
    return console, buffer


def test_print_downloaded_config_notice_reports_success() -> None:
    console, buffer = _console_buffer()

    _print_downloaded_config_notice(
        console, config_output_path="foo.py", config_written=True
    )

    assert "Workflow config downloaded to 'foo.py'" in buffer.getvalue()


def test_print_downloaded_config_notice_reports_missing_config() -> None:
    console, buffer = _console_buffer()

    _print_downloaded_config_notice(
        console, config_output_path="foo.py", config_written=False
    )

    assert "skipped config download" in buffer.getvalue()
