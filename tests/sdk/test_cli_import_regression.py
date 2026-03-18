"""Regression tests for CLI import cycles."""

from __future__ import annotations
import importlib
import sys


def test_cli_main_imports_without_circular_plugin_error() -> None:
    """Importing the CLI entrypoint should not trip listener/plugin cycles."""
    saved_modules = {
        name: mod
        for name, mod in sys.modules.items()
        if name == "orcheo_sdk"
        or name.startswith("orcheo_sdk.")
        or name == "orcheo"
        or name.startswith("orcheo.")
    }
    try:
        for module_name in list(saved_modules):
            sys.modules.pop(module_name, None)

        module = importlib.import_module("orcheo_sdk.cli.main")

        assert module.app is not None
    finally:
        # Restore original modules so later tests see the same class objects
        # (prevents isinstance failures from reloaded classes).
        for module_name in list(sys.modules):
            if module_name == "orcheo_sdk" or module_name.startswith("orcheo_sdk."):
                sys.modules.pop(module_name, None)
            if module_name == "orcheo" or module_name.startswith("orcheo."):
                sys.modules.pop(module_name, None)
        sys.modules.update(saved_modules)
