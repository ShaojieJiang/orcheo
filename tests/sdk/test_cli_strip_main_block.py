"""Helpers for stripping __main__ blocks from scripts."""

from __future__ import annotations
from pathlib import Path


def test_strip_main_block_single_quotes(tmp_path: Path) -> None:
    """Test _strip_main_block removes if __name__ with single quotes."""
    from orcheo_sdk.cli.workflow import _strip_main_block

    script = """
def hello():
    return "world"

if __name__ == '__main__':
    hello()
"""
    result = _strip_main_block(script)
    assert "if __name__" not in result
    assert "    hello()" not in result
    assert "def hello():" in result


def test_strip_main_block_double_quotes(tmp_path: Path) -> None:
    """Test _strip_main_block removes if __name__ with double quotes."""
    from orcheo_sdk.cli.workflow import _strip_main_block

    script = """
def hello():
    return "world"

if __name__ == "__main__":
    hello()
"""
    result = _strip_main_block(script)
    assert "if __name__" not in result
    assert "    hello()" not in result
    assert "def hello():" in result
