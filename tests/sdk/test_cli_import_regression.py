"""Regression tests for CLI import cycles."""

from __future__ import annotations
import importlib
import sys


def test_cli_main_imports_without_circular_plugin_error() -> None:
    """Importing the CLI entrypoint should not trip listener/plugin cycles."""
    for module_name in list(sys.modules):
        if module_name == "orcheo_sdk" or module_name.startswith("orcheo_sdk."):
            sys.modules.pop(module_name, None)
        if module_name == "orcheo" or module_name.startswith("orcheo."):
            sys.modules.pop(module_name, None)

    module = importlib.import_module("orcheo_sdk.cli.main")

    assert module.app is not None
