"""Tests for the CLI config command."""

from __future__ import annotations
import tomllib
from pathlib import Path
import pytest
from typer.testing import CliRunner
from orcheo_sdk.cli.config import CONFIG_FILENAME, PROFILE_ENV
from orcheo_sdk.cli.config_command import (
    _format_toml_value,
    _read_env_file,
    _resolve_value,
)
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.main import app


def test_config_command_writes_profiles_from_env_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "ORCHEO_API_URL=http://env-file.test",
                "ORCHEO_SERVICE_TOKEN=env-token",
                "ORCHEO_CHATKIT_PUBLIC_BASE_URL=http://canvas.test",
                "ORCHEO_AUTH_ISSUER=https://auth.env-file.test",
                "ORCHEO_AUTH_CLIENT_ID=env-client-id",
                "ORCHEO_AUTH_SCOPES=openid email",
                "ORCHEO_AUTH_AUDIENCE=https://api.env-file.test",
                "ORCHEO_AUTH_ORGANIZATION=org-env",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["config", "--env-file", str(env_file), "--profile", "default", "-p", "local"],
        env=env,
    )

    assert result.exit_code == 0

    config_path = Path(env["ORCHEO_CONFIG_DIR"]) / CONFIG_FILENAME
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    profiles = data["profiles"]

    for profile_name in ("default", "local"):
        profile = profiles[profile_name]
        assert profile["api_url"] == "http://env-file.test"
        assert profile["service_token"] == "env-token"
        assert profile["chatkit_public_base_url"] == "http://canvas.test"
        assert profile["ORCHEO_AUTH_ISSUER"] == "https://auth.env-file.test"
        assert profile["ORCHEO_AUTH_CLIENT_ID"] == "env-client-id"
        assert profile["ORCHEO_AUTH_SCOPES"] == "openid email"
        assert profile["ORCHEO_AUTH_AUDIENCE"] == "https://api.env-file.test"
        assert profile["ORCHEO_AUTH_ORGANIZATION"] == "org-env"


def test_config_command_uses_environment_defaults(
    runner: CliRunner, env: dict[str, str]
) -> None:
    result = runner.invoke(app, ["config"], env=env)

    assert result.exit_code == 0

    config_path = Path(env["ORCHEO_CONFIG_DIR"]) / CONFIG_FILENAME
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    profile = data["profiles"]["default"]

    assert profile["api_url"] == env["ORCHEO_API_URL"]
    assert profile["service_token"] == env["ORCHEO_SERVICE_TOKEN"]


def test_config_command_without_service_token(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Test config command works without service token (covers falsy branch)."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    env_without_token = {
        "ORCHEO_CONFIG_DIR": str(config_dir),
        "ORCHEO_CACHE_DIR": str(tmp_path / "cache"),
        "ORCHEO_API_URL": "http://api.test",
        "ORCHEO_HUMAN": "1",
        "NO_COLOR": "1",
    }

    result = runner.invoke(app, ["config"], env=env_without_token)

    assert result.exit_code == 0

    config_path = config_dir / CONFIG_FILENAME
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    profile = data["profiles"]["default"]

    assert profile["api_url"] == "http://api.test"
    assert "service_token" not in profile


def test_read_env_file_not_found(tmp_path: Path) -> None:
    """Test CLIError raised when env file does not exist."""
    missing = tmp_path / "missing.env"
    with pytest.raises(CLIError) as exc_info:
        _read_env_file(missing)
    assert "not found" in str(exc_info.value)


def test_read_env_file_skips_comments_and_empty_lines(tmp_path: Path) -> None:
    """Test that comments, empty lines, and lines without '=' are skipped."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# This is a comment",
                "",
                "   ",
                "VALID_KEY=value",
                "no_equals_sign",
                "ANOTHER=another_value",
            ]
        ),
        encoding="utf-8",
    )
    data = _read_env_file(env_file)
    assert data == {"VALID_KEY": "value", "ANOTHER": "another_value"}


def test_read_env_file_handles_export_prefix(tmp_path: Path) -> None:
    """Test that export prefix is stripped from env lines."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "export MY_VAR=exported_value",
                "NORMAL_VAR=normal_value",
            ]
        ),
        encoding="utf-8",
    )
    data = _read_env_file(env_file)
    assert data["MY_VAR"] == "exported_value"
    assert data["NORMAL_VAR"] == "normal_value"


def test_read_env_file_handles_quoted_values(tmp_path: Path) -> None:
    """Test that quoted values have quotes stripped."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                'DOUBLE_QUOTED="double quoted value"',
                "SINGLE_QUOTED='single quoted value'",
                "UNQUOTED=unquoted_value",
            ]
        ),
        encoding="utf-8",
    )
    data = _read_env_file(env_file)
    assert data["DOUBLE_QUOTED"] == "double quoted value"
    assert data["SINGLE_QUOTED"] == "single quoted value"
    assert data["UNQUOTED"] == "unquoted_value"


def test_resolve_value_prefers_override() -> None:
    """Test that override parameter takes precedence."""
    result = _resolve_value(
        "ANY_KEY",
        env_data={"ANY_KEY": "env_value"},
        override="override_value",
    )
    assert result == "override_value"


def test_format_toml_value_bool() -> None:
    """Test formatting boolean values."""
    assert _format_toml_value(True) == "true"
    assert _format_toml_value(False) == "false"


def test_format_toml_value_numeric() -> None:
    """Test formatting integer and float values."""
    assert _format_toml_value(42) == "42"
    assert _format_toml_value(3.14) == "3.14"


def test_format_toml_value_list() -> None:
    """Test formatting list values."""
    assert _format_toml_value(["a", "b"]) == '["a", "b"]'
    assert _format_toml_value([1, 2, 3]) == "[1, 2, 3]"


def test_format_toml_value_unsupported_type() -> None:
    """Test that unsupported types raise CLIError."""
    with pytest.raises(CLIError) as exc_info:
        _format_toml_value({"key": "value"})
    assert "Unsupported config value type" in str(exc_info.value)


def test_config_command_uses_profile_from_env_file(
    runner: CliRunner, env: dict[str, str], tmp_path: Path
) -> None:
    """Test that ORCHEO_PROFILE from env file is used as default profile name."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"{PROFILE_ENV}=custom-profile",
                "ORCHEO_API_URL=http://custom.test",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["config", "--env-file", str(env_file)],
        env=env,
    )

    assert result.exit_code == 0

    config_path = Path(env["ORCHEO_CONFIG_DIR"]) / CONFIG_FILENAME
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert "custom-profile" in data["profiles"]
    assert data["profiles"]["custom-profile"]["api_url"] == "http://custom.test"


def test_config_command_missing_api_url(runner: CliRunner, tmp_path: Path) -> None:
    """Test that missing API URL raises CLIError."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    minimal_env = {
        "ORCHEO_CONFIG_DIR": str(config_dir),
        "ORCHEO_API_URL": "",
        "ORCHEO_HUMAN": "1",
        "NO_COLOR": "1",
    }

    result = runner.invoke(app, ["config"], env=minimal_env)

    assert result.exit_code == 1
    assert isinstance(result.exception, CLIError)
    assert "ORCHEO_API_URL" in str(result.exception)


def test_config_command_invalid_toml(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str]
) -> None:
    """Test that invalid TOML in existing config raises CLIError."""
    import tomllib
    from unittest.mock import MagicMock
    from rich.console import Console
    from typer import Context
    from orcheo_sdk.cli import config_command
    from orcheo_sdk.cli.config_command import configure

    # Set environment variables
    monkeypatch.setenv("ORCHEO_CONFIG_DIR", env["ORCHEO_CONFIG_DIR"])
    monkeypatch.setenv("ORCHEO_API_URL", env["ORCHEO_API_URL"])

    # Create a real TOMLDecodeError by parsing invalid TOML
    try:
        tomllib.loads("[[")
    except tomllib.TOMLDecodeError as toml_error:
        captured_error = toml_error

    # Patch load_profiles to raise TOMLDecodeError as it would with invalid TOML
    def _raise_toml_error(path: Path) -> dict[str, dict[str, str]]:
        raise captured_error

    monkeypatch.setattr(config_command, "load_profiles", _raise_toml_error)

    # Create a mock context that provides a console
    mock_state = MagicMock()
    mock_state.console = Console()
    mock_ctx = MagicMock(spec=Context)
    mock_ctx.ensure_object.return_value = mock_state

    with pytest.raises(CLIError) as exc_info:
        configure(
            ctx=mock_ctx,
            profile=None,
            api_url=env["ORCHEO_API_URL"],
            service_token=None,
            chatkit_public_base_url=None,
            env_file=None,
        )

    assert "Invalid TOML" in str(exc_info.value)


def test_resolve_oauth_values_all_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover false branches when no OAuth values resolve."""
    from orcheo_sdk.cli.auth.config import (
        AUTH_AUDIENCE_ENV,
        AUTH_CLIENT_ID_ENV,
        AUTH_ISSUER_ENV,
        AUTH_ORGANIZATION_ENV,
        AUTH_SCOPES_ENV,
    )
    from orcheo_sdk.cli.config_command import _resolve_oauth_values

    for key in [
        AUTH_ISSUER_ENV,
        AUTH_CLIENT_ID_ENV,
        AUTH_SCOPES_ENV,
        AUTH_AUDIENCE_ENV,
        AUTH_ORGANIZATION_ENV,
    ]:
        monkeypatch.delenv(key, raising=False)

    result = _resolve_oauth_values(
        env_data=None,
        auth_issuer=None,
        auth_client_id=None,
        auth_scopes=None,
        auth_audience=None,
        auth_organization=None,
    )
    assert result == {}
