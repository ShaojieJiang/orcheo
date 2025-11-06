"""Error class behaviour tests for the CLI."""

from __future__ import annotations
from orcheo_sdk.cli.errors import CLIConfigurationError, CLIError


def test_cli_error_instantiation() -> None:
    error = CLIError("Test error")
    assert str(error) == "Test error"


def test_cli_configuration_error_instantiation() -> None:
    error = CLIConfigurationError("Config error")
    assert str(error) == "Config error"
    assert isinstance(error, CLIError)
